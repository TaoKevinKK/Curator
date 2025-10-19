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
Adapter layer that converts user-defined actors (from base_actors.py) 
into Ray Data executable format, similar to how adapter.py works for ProcessingStage.
"""

from typing import Any, Type
import numpy as np
from pyarrow import Table
from ray.data import Dataset, ActorPoolStrategy

from .base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
    BaseRayMapBatchPyarrowActor,
    BaseRayDatasetActor,
)


class BaseActorAdapter:
    """Base adapter that converts user-defined actors to Ray Data executable format.
    
    This adapter allows users to define actors using base_actors.py abstractions
    while executing them through Ray Data's map_batches/flat_map APIs.
    """
    
    def __init__(
        self,
        actor_class: Type,
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        """Initialize the actor adapter.
        
        Args:
            actor_class: The user-defined actor class (subclass of BaseRayActor)
            actor_kwargs: Keyword arguments to pass to actor constructor
            batch_size: Batch size for processing (for map_batches operations)
            num_cpus: Number of CPUs per actor/task
            num_gpus: Number of GPUs per actor/task
            concurrency: Concurrency for actor pool (int or (min, max) tuple)
        """
        self.actor_class = actor_class
        self.actor_kwargs = actor_kwargs or {}
        self.batch_size = batch_size
        self.num_cpus = num_cpus
        self.num_gpus = num_gpus
        self.concurrency = concurrency
    
    def _get_compute_kwargs(self) -> dict[str, Any]:
        """Get compute resource kwargs for Ray Data operations."""
        kwargs = {}
        if self.num_cpus is not None:
            kwargs["num_cpus"] = self.num_cpus
        if self.num_gpus is not None:
            kwargs["num_gpus"] = self.num_gpus
        if self.concurrency is not None:
            kwargs["concurrency"] = self.concurrency
        return kwargs
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """Process a Ray Data dataset through the user-defined actor.
        
        Args:
            dataset: Input Ray Data dataset
            
        Returns:
            Processed Ray Data dataset
        """
        raise NotImplementedError("Subclasses must implement process_dataset")


class FlatMapActorAdapter(BaseActorAdapter):
    """Adapter for BaseRayFlatMapActor subclasses.
    
    Converts row-level flat_map operations into Ray Data's flat_map API.
    User's actor processes single rows and can return multiple rows per input.
    """
    
    def __init__(
        self,
        actor_class: Type[BaseRayFlatMapActor],
        actor_kwargs: dict[str, Any] | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        super().__init__(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=None,  # flat_map doesn't use batch_size
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """Process dataset using flat_map with the user-defined actor."""
        # Determine if we should use actors or tasks
        use_actors = self.concurrency is not None or self.num_gpus is not None
        
        if use_actors:
            # Create actor class wrapper
            actor_wrapper = self._create_actor_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.flat_map(actor_wrapper, **compute_kwargs)
        else:
            # Create task function wrapper
            task_wrapper = self._create_task_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.flat_map(task_wrapper, **compute_kwargs)
    
    def _create_actor_wrapper(self) -> Type:
        """Create an actor class that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        class FlatMapActorWrapper:
            def __init__(self):
                self.actor_instance = actor_class(**actor_kwargs)
            
            def __call__(self, row: dict[str, Any]) -> list[dict[str, Any]]:
                return self.actor_instance(row)
        
        # Set meaningful name
        wrapper_name = f"{actor_class.__name__}Wrapper"
        FlatMapActorWrapper.__name__ = wrapper_name
        FlatMapActorWrapper.__qualname__ = wrapper_name
        
        return FlatMapActorWrapper
    
    def _create_task_wrapper(self):
        """Create a task function that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        def flat_map_task(row: dict[str, Any]) -> list[dict[str, Any]]:
            actor_instance = actor_class(**actor_kwargs)
            return actor_instance(row)
        
        # Set meaningful name
        task_name = f"{actor_class.__name__}Task"
        flat_map_task.__name__ = task_name
        flat_map_task.__qualname__ = task_name
        
        return flat_map_task


class MapBatchActorAdapter(BaseActorAdapter):
    """Adapter for BaseRayMapBatchActor subclasses.
    
    Converts batch-level map operations (numpy format) into Ray Data's map_batches API.
    User's actor processes batches in dictionary of numpy arrays format.
    """
    
    def __init__(
        self,
        actor_class: Type[BaseRayMapBatchActor],
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        super().__init__(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=batch_size,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """Process dataset using map_batches with the user-defined actor."""
        # Determine if we should use actors or tasks
        use_actors = self.concurrency is not None or self.num_gpus is not None
        
        if use_actors:
            # Create actor class wrapper
            actor_wrapper = self._create_actor_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.map_batches(
                actor_wrapper,
                batch_size=self.batch_size,
                batch_format="numpy",
                **compute_kwargs
            )
        else:
            # Create task function wrapper
            task_wrapper = self._create_task_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.map_batches(
                task_wrapper,
                batch_size=self.batch_size,
                batch_format="numpy",
                **compute_kwargs
            )
    
    def _create_actor_wrapper(self) -> Type:
        """Create an actor class that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        class MapBatchActorWrapper:
            def __init__(self):
                self.actor_instance = actor_class(**actor_kwargs)
            
            def __call__(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
                return self.actor_instance(batch)
        
        # Set meaningful name
        wrapper_name = f"{actor_class.__name__}Wrapper"
        MapBatchActorWrapper.__name__ = wrapper_name
        MapBatchActorWrapper.__qualname__ = wrapper_name
        
        return MapBatchActorWrapper
    
    def _create_task_wrapper(self):
        """Create a task function that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        def map_batch_task(batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
            actor_instance = actor_class(**actor_kwargs)
            return actor_instance(batch)
        
        # Set meaningful name
        task_name = f"{actor_class.__name__}Task"
        map_batch_task.__name__ = task_name
        map_batch_task.__qualname__ = task_name
        
        return map_batch_task


class MapBatchPyarrowActorAdapter(BaseActorAdapter):
    """Adapter for BaseRayMapBatchPyarrowActor subclasses.
    
    Converts batch-level map operations (PyArrow format) into Ray Data's map_batches API.
    User's actor processes batches in PyArrow Table format.
    """
    
    def __init__(
        self,
        actor_class: Type[BaseRayMapBatchPyarrowActor],
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        super().__init__(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=batch_size,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """Process dataset using map_batches with the user-defined actor."""
        # Determine if we should use actors or tasks
        use_actors = self.concurrency is not None or self.num_gpus is not None
        
        if use_actors:
            # Create actor class wrapper
            actor_wrapper = self._create_actor_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.map_batches(
                actor_wrapper,
                batch_size=self.batch_size,
                batch_format="pyarrow",
                **compute_kwargs
            )
        else:
            # Create task function wrapper
            task_wrapper = self._create_task_wrapper()
            compute_kwargs = self._get_compute_kwargs()
            return dataset.map_batches(
                task_wrapper,
                batch_size=self.batch_size,
                batch_format="pyarrow",
                **compute_kwargs
            )
    
    def _create_actor_wrapper(self) -> Type:
        """Create an actor class that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        class MapBatchPyarrowActorWrapper:
            def __init__(self):
                self.actor_instance = actor_class(**actor_kwargs)
            
            def __call__(self, table: Table) -> Table:
                return self.actor_instance(table)
        
        # Set meaningful name
        wrapper_name = f"{actor_class.__name__}Wrapper"
        MapBatchPyarrowActorWrapper.__name__ = wrapper_name
        MapBatchPyarrowActorWrapper.__qualname__ = wrapper_name
        
        return MapBatchPyarrowActorWrapper
    
    def _create_task_wrapper(self):
        """Create a task function that wraps the user-defined actor."""
        actor_class = self.actor_class
        actor_kwargs = self.actor_kwargs
        
        def map_batch_pyarrow_task(table: Table) -> Table:
            actor_instance = actor_class(**actor_kwargs)
            return actor_instance(table)
        
        # Set meaningful name
        task_name = f"{actor_class.__name__}Task"
        map_batch_pyarrow_task.__name__ = task_name
        map_batch_pyarrow_task.__qualname__ = task_name
        
        return map_batch_pyarrow_task


class DatasetActorAdapter(BaseActorAdapter):
    """Adapter for BaseRayDatasetActor subclasses.
    
    Converts dataset-level operations into Ray Data's map_batches API.
    User's actor processes entire datasets, but we execute them in a distributed manner.
    
    Note: This is a special case where the actor operates on Dataset level,
    so we use map_batches with special handling or window operations.
    """
    
    def __init__(
        self,
        actor_class: Type[BaseRayDatasetActor],
        actor_kwargs: dict[str, Any] | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        super().__init__(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=None,  # Dataset operations don't use batch_size
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """Process dataset using the user-defined dataset actor.
        
        Note: Dataset actors operate on the entire dataset, so we directly
        instantiate the actor and call it with the dataset.
        """
        actor_instance = self.actor_class(**self.actor_kwargs)
        return actor_instance(dataset)


def create_adapter_for_actor(
    actor_class: Type,
    actor_kwargs: dict[str, Any] | None = None,
    batch_size: int | None = None,
    num_cpus: float | None = None,
    num_gpus: float | None = None,
    concurrency: int | tuple[int, int] | None = None,
) -> BaseActorAdapter:
    """Factory function to create the appropriate adapter for a given actor class.
    
    Args:
        actor_class: The user-defined actor class (subclass of BaseRayActor)
        actor_kwargs: Keyword arguments to pass to actor constructor
        batch_size: Batch size for processing (for map_batches operations)
        num_cpus: Number of CPUs per actor/task
        num_gpus: Number of GPUs per actor/task
        concurrency: Concurrency for actor pool (int or (min, max) tuple)
        
    Returns:
        Appropriate adapter instance based on actor type
        
    Raises:
        ValueError: If actor_class is not a recognized BaseRayActor subclass
    """
    if issubclass(actor_class, BaseRayFlatMapActor):
        return FlatMapActorAdapter(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    elif issubclass(actor_class, BaseRayMapBatchPyarrowActor):
        # Check PyArrow before MapBatch since it might inherit from it
        return MapBatchPyarrowActorAdapter(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=batch_size,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    elif issubclass(actor_class, BaseRayMapBatchActor):
        return MapBatchActorAdapter(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            batch_size=batch_size,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    elif issubclass(actor_class, BaseRayDatasetActor):
        return DatasetActorAdapter(
            actor_class=actor_class,
            actor_kwargs=actor_kwargs,
            num_cpus=num_cpus,
            num_gpus=num_gpus,
            concurrency=concurrency,
        )
    else:
        raise ValueError(
            f"actor_class must be a subclass of BaseRayFlatMapActor, "
            f"BaseRayMapBatchActor, BaseRayMapBatchPyarrowActor, or "
            f"BaseRayDatasetActor, but got {actor_class}"
        )

