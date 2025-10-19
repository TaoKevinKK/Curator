# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Xenna Actor Adapter - 将 BaseRayActor 转换为 Xenna Stage

这个适配器允许用户使用 base_actors.py 中定义的 Actor 抽象，
但底层通过 Xenna 的调度机制直接执行（不使用 Ray Data）。
"""

from typing import Any, Type
import numpy as np
from pyarrow import Table
import pyarrow as pa

from cosmos_xenna.pipelines import v1 as pipelines_v1
from cosmos_xenna.ray_utils.resources import Resources as XennaResources
from cosmos_xenna.ray_utils.resources import NodeInfo as XennaNodeInfo
from cosmos_xenna.ray_utils.resources import WorkerMetadata as XennaWorkerMetadata

from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayActor,
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
    BaseRayMapBatchPyarrowActor,
    BaseRayDatasetActor,
)
from nemo_curator.tasks import Task


class XennaActorStageAdapter(pipelines_v1.Stage):
    """
    Base adapter that converts user-defined BaseRayActor to Xenna Stage.
    
    This adapter bridges the gap between:
    - User's Actor definition (BaseRayActor subclasses)
    - Xenna's execution model (pipelines_v1.Stage)
    
    The adapter handles:
    - Resource requirements
    - Setup lifecycle
    - Data processing delegation to user's Actor
    """
    
    def __init__(
        self,
        actor_class: Type[BaseRayActor],
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        resources: XennaResources | None = None,
    ):
        """Initialize the Xenna Actor adapter.
        
        Args:
            actor_class: User-defined Actor class (subclass of BaseRayActor)
            actor_kwargs: Keyword arguments to pass to actor constructor
            batch_size: Batch size for processing (default: 1)
            resources: Xenna resources for this stage
        """
        self.actor_class = actor_class
        self.actor_kwargs = actor_kwargs or {}
        self._batch_size = batch_size or 1
        self._resources = resources or XennaResources(cpus=1)
        self._actor_instance = None
    
    @property
    def required_resources(self) -> XennaResources:
        """Get the resources required for this stage."""
        return self._resources
    
    @property
    def stage_batch_size(self) -> int:
        """Get the batch size for this stage."""
        return self._batch_size
    
    @property
    def env_info(self) -> pipelines_v1.RuntimeEnv | None:
        """Runtime environment for this stage."""
        return None
    
    def setup_on_node(self, node_info: XennaNodeInfo, worker_metadata: XennaWorkerMetadata) -> None:
        """Setup the actor on a node.
        
        Args:
            node_info: Xenna's NodeInfo object
            worker_metadata: Xenna's WorkerMetadata object
        """
        # Create actor instance if not already created
        if self._actor_instance is None:
            self._actor_instance = self.actor_class(**self.actor_kwargs)
    
    def setup(self, worker_metadata: XennaWorkerMetadata) -> None:
        """Setup the actor per worker.
        
        Args:
            worker_metadata: Xenna's WorkerMetadata object
        """
        # Ensure actor instance is created
        if self._actor_instance is None:
            self._actor_instance = self.actor_class(**self.actor_kwargs)
    
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """Process tasks - to be implemented by subclasses.
        
        Args:
            tasks: List of tasks to process
            
        Returns:
            List of processed tasks or None
        """
        raise NotImplementedError("Subclasses must implement process_data")


class FlatMapActorStageAdapter(XennaActorStageAdapter):
    """
    Adapter for BaseRayFlatMapActor that processes tasks one-by-one.
    
    This adapter:
    - Takes a list of Task objects
    - Converts each Task to a dict
    - Calls user's _call() method (which returns list of dicts)
    - Converts results back to Task objects
    """
    
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """Process tasks using FlatMap actor.
        
        Args:
            tasks: List of input tasks
            
        Returns:
            List of output tasks (flattened)
        """
        if not tasks:
            return []
        
        output_tasks = []
        
        for task in tasks:
            # Convert Task to dict
            row = task.to_dict() if hasattr(task, 'to_dict') else {"task": task}
            
            # Call user's actor
            results = self._actor_instance(row)
            
            # Convert results back to Tasks
            for result_dict in results:
                # Create new Task from result
                output_task = Task.from_dict(result_dict) if hasattr(Task, 'from_dict') else Task(**result_dict)
                output_tasks.append(output_task)
        
        return output_tasks if output_tasks else None


class MapBatchActorStageAdapter(XennaActorStageAdapter):
    """
    Adapter for BaseRayMapBatchActor that processes tasks in batches (numpy format).
    
    This adapter:
    - Takes a batch of Task objects
    - Converts to numpy batch format (dict of arrays)
    - Calls user's _call() method
    - Converts results back to Task objects
    """
    
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """Process tasks using MapBatch actor.
        
        Args:
            tasks: List of input tasks
            
        Returns:
            List of output tasks
        """
        if not tasks:
            return []
        
        # Convert tasks to batch format (dict of numpy arrays)
        batch = self._tasks_to_numpy_batch(tasks)
        
        # Call user's actor
        result_batch = self._actor_instance(batch)
        
        # Convert results back to tasks
        output_tasks = self._numpy_batch_to_tasks(result_batch, tasks)
        
        return output_tasks if output_tasks else None
    
    def _tasks_to_numpy_batch(self, tasks: list[Task]) -> dict[str, np.ndarray]:
        """Convert list of Task objects to numpy batch format.
        
        Args:
            tasks: List of Task objects
            
        Returns:
            Dictionary of numpy arrays
        """
        # Extract attributes from tasks
        # Assuming tasks have common attributes
        batch_dict = {}
        
        if not tasks:
            return batch_dict
        
        # Get sample task to determine structure
        sample_task = tasks[0]
        task_dict = sample_task.to_dict() if hasattr(sample_task, 'to_dict') else sample_task.__dict__
        
        # Build batch dict
        for key in task_dict.keys():
            values = []
            for task in tasks:
                task_data = task.to_dict() if hasattr(task, 'to_dict') else task.__dict__
                values.append(task_data.get(key))
            
            # Convert to numpy array
            try:
                batch_dict[key] = np.array(values)
            except (ValueError, TypeError):
                # If can't convert to array, keep as list
                batch_dict[key] = np.array(values, dtype=object)
        
        return batch_dict
    
    def _numpy_batch_to_tasks(self, batch: dict[str, np.ndarray], original_tasks: list[Task]) -> list[Task]:
        """Convert numpy batch to list of Task objects.
        
        Args:
            batch: Dictionary of numpy arrays
            original_tasks: Original task objects (for merging)
            
        Returns:
            List of Task objects
        """
        if not batch:
            return []
        
        # Determine batch size
        batch_size = len(next(iter(batch.values())))
        
        output_tasks = []
        for i in range(batch_size):
            # Extract row from batch
            row_dict = {key: values[i] for key, values in batch.items()}
            
            # Merge with original task if available
            if i < len(original_tasks):
                original_dict = original_tasks[i].to_dict() if hasattr(original_tasks[i], 'to_dict') else original_tasks[i].__dict__
                row_dict = {**original_dict, **row_dict}
            
            # Create Task from row
            task = Task.from_dict(row_dict) if hasattr(Task, 'from_dict') else Task(**row_dict)
            output_tasks.append(task)
        
        return output_tasks


class MapBatchPyarrowActorStageAdapter(XennaActorStageAdapter):
    """
    Adapter for BaseRayMapBatchPyarrowActor that processes tasks in PyArrow format.
    
    This adapter:
    - Takes a batch of Task objects
    - Converts to PyArrow Table format
    - Calls user's _call() method
    - Converts results back to Task objects
    """
    
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """Process tasks using MapBatch PyArrow actor.
        
        Args:
            tasks: List of input tasks
            
        Returns:
            List of output tasks
        """
        if not tasks:
            return []
        
        # Convert tasks to PyArrow table
        table = self._tasks_to_pyarrow_table(tasks)
        
        # Call user's actor
        result_table = self._actor_instance(table)
        
        # Convert results back to tasks
        output_tasks = self._pyarrow_table_to_tasks(result_table)
        
        return output_tasks if output_tasks else None
    
    def _tasks_to_pyarrow_table(self, tasks: list[Task]) -> Table:
        """Convert list of Task objects to PyArrow Table.
        
        Args:
            tasks: List of Task objects
            
        Returns:
            PyArrow Table
        """
        # Convert tasks to list of dicts
        rows = []
        for task in tasks:
            task_dict = task.to_dict() if hasattr(task, 'to_dict') else task.__dict__
            rows.append(task_dict)
        
        # Convert to PyArrow table
        if rows:
            return pa.Table.from_pylist(rows)
        else:
            return pa.table({})
    
    def _pyarrow_table_to_tasks(self, table: Table) -> list[Task]:
        """Convert PyArrow Table to list of Task objects.
        
        Args:
            table: PyArrow Table
            
        Returns:
            List of Task objects
        """
        if table.num_rows == 0:
            return []
        
        # Convert table to list of dicts
        rows = table.to_pylist()
        
        # Create Task objects
        output_tasks = []
        for row_dict in rows:
            task = Task.from_dict(row_dict) if hasattr(Task, 'from_dict') else Task(**row_dict)
            output_tasks.append(task)
        
        return output_tasks


class DatasetActorStageAdapter(XennaActorStageAdapter):
    """
    Adapter for BaseRayDatasetActor that operates on task collections.
    
    Note: Since BaseRayDatasetActor operates on Ray Datasets and Xenna operates on
    list of Tasks, this adapter provides a simpler interface where the actor
    receives and returns list of Task objects directly.
    """
    
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """Process tasks using Dataset actor.
        
        For Dataset-level actors, we pass the entire task list to the actor.
        The actor should handle the logic internally.
        
        Args:
            tasks: List of input tasks
            
        Returns:
            List of output tasks
        """
        if not tasks:
            return []
        
        # For Dataset actors, we need to provide a dataset-like interface
        # Since Xenna doesn't use Ray Data, we pass tasks directly
        # The actor should be modified to work with list of tasks instead of Dataset
        
        # Note: This is a simplified version. In practice, you might want to
        # create a wrapper that makes list[Task] look like a Dataset
        result_tasks = self._actor_instance(tasks)
        
        return result_tasks if result_tasks else None


def create_xenna_actor_stage(
    actor_class: Type[BaseRayActor],
    actor_kwargs: dict[str, Any] | None = None,
    batch_size: int | None = None,
    num_cpus: float = 1.0,
    num_gpus: float = 0.0,
    nvdecs: int = 0,
    nvencs: int = 0,
    entire_gpu: bool = False,
) -> XennaActorStageAdapter:
    """Factory function to create Xenna Stage from BaseRayActor.
    
    This function automatically selects the appropriate adapter based on the
    actor class type and configures resources.
    
    Args:
        actor_class: User-defined Actor class (subclass of BaseRayActor)
        actor_kwargs: Keyword arguments to pass to actor constructor
        batch_size: Batch size for processing (default: 1 for FlatMap, 32 for MapBatch)
        num_cpus: Number of CPUs per worker
        num_gpus: Number of GPUs per worker
        nvdecs: Number of video decoders
        nvencs: Number of video encoders
        entire_gpu: Whether to allocate entire GPU
        
    Returns:
        XennaActorStageAdapter: Xenna Stage that can be used in a pipeline
        
    Raises:
        ValueError: If actor_class is not a recognized BaseRayActor subclass
    """
    # Create Xenna resources
    resources = XennaResources(
        cpus=num_cpus,
        gpus=num_gpus,
        nvdecs=nvdecs,
        nvencs=nvencs,
        entire_gpu=entire_gpu,
    )
    
    # Determine batch size if not specified
    if batch_size is None:
        if issubclass(actor_class, BaseRayFlatMapActor):
            batch_size = 1  # FlatMap typically processes one at a time
        else:
            batch_size = 32  # Default batch size for batch operations
    
    # Select appropriate adapter based on actor type
    if issubclass(actor_class, BaseRayFlatMapActor):
        adapter_class = FlatMapActorStageAdapter
    elif issubclass(actor_class, BaseRayMapBatchPyarrowActor):
        # Check PyArrow before MapBatch since it might inherit from it
        adapter_class = MapBatchPyarrowActorStageAdapter
    elif issubclass(actor_class, BaseRayMapBatchActor):
        adapter_class = MapBatchActorStageAdapter
    elif issubclass(actor_class, BaseRayDatasetActor):
        adapter_class = DatasetActorStageAdapter
    else:
        raise ValueError(
            f"actor_class must be a subclass of BaseRayFlatMapActor, "
            f"BaseRayMapBatchActor, BaseRayMapBatchPyarrowActor, or "
            f"BaseRayDatasetActor, but got {actor_class}"
        )
    
    # Create and return adapter
    adapter = adapter_class(
        actor_class=actor_class,
        actor_kwargs=actor_kwargs,
        batch_size=batch_size,
        resources=resources,
    )
    
    # Set the adapter's class name to match the actor for better logging
    adapter_class_name = f"{actor_class.__name__}XennaStage"
    
    # Create dynamic subclass with meaningful name
    DynamicAdapter = type(
        adapter_class_name,
        (adapter_class,),
        {"__module__": adapter.__module__},
    )
    
    # Return instance of dynamic adapter
    return DynamicAdapter(
        actor_class=actor_class,
        actor_kwargs=actor_kwargs,
        batch_size=batch_size,
        resources=resources,
    )

