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
Example usage of the actor adapter layer.

This demonstrates how users can define actors using base_actors.py abstractions
and execute them through Ray Data using the adapter layer.
"""

from typing import Any
import numpy as np
from pyarrow import Table
import pyarrow as pa
import ray
from ray.data import Dataset

from .base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
    BaseRayMapBatchPyarrowActor,
    BaseRayDatasetActor,
)
from .actor_adapter import create_adapter_for_actor


# ========== Example 1: FlatMap Actor ==========

class TextSplitterActor(BaseRayFlatMapActor):
    """Example actor that splits text into words."""
    
    def __init__(self, exclude_columns: list[str] | None = None):
        super().__init__(exclude_columns)
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Split text into multiple rows, one per word."""
        text = row.get("text", "")
        words = text.split()
        return [{"word": word, "length": len(word)} for word in words]


def example_flatmap():
    """Example usage of FlatMap actor."""
    # Create sample dataset
    ds = ray.data.from_items([
        {"id": 1, "text": "hello world"},
        {"id": 2, "text": "ray data processing"},
    ])
    
    # Create adapter for the actor
    adapter = create_adapter_for_actor(
        actor_class=TextSplitterActor,
        actor_kwargs={"exclude_columns": ["id"]},
        num_cpus=1,
        concurrency=2,  # Use 2 actors
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    
    print("FlatMap Example Results:")
    print(result_ds.take_all())
    return result_ds


# ========== Example 2: MapBatch Actor (Numpy) ==========

class NormalizationActor(BaseRayMapBatchActor):
    """Example actor that normalizes numerical values."""
    
    def __init__(self, exclude_columns: list[str] | None = None):
        super().__init__(exclude_columns)
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Normalize values in the batch."""
        values = batch.get("value", np.array([]))
        if len(values) > 0:
            mean = np.mean(values)
            std = np.std(values)
            normalized = (values - mean) / (std + 1e-8)
            return {"normalized_value": normalized}
        return {"normalized_value": np.array([])}


def example_map_batch_numpy():
    """Example usage of MapBatch actor with numpy format."""
    # Create sample dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 10.0},
        {"id": 2, "value": 20.0},
        {"id": 3, "value": 30.0},
        {"id": 4, "value": 40.0},
    ])
    
    # Create adapter for the actor
    adapter = create_adapter_for_actor(
        actor_class=NormalizationActor,
        actor_kwargs={"exclude_columns": None},
        batch_size=2,
        num_cpus=1,
        concurrency=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    
    print("\nMapBatch (Numpy) Example Results:")
    print(result_ds.take_all())
    return result_ds


# ========== Example 3: MapBatch Actor (PyArrow) ==========

class ColumnRenameActor(BaseRayMapBatchPyarrowActor):
    """Example actor that processes PyArrow tables."""
    
    def __init__(self, prefix: str = "new_", exclude_columns: list[str] | None = None):
        super().__init__(exclude_columns)
        self.prefix = prefix
    
    def _call(self, table: Table) -> Table:
        """Add prefix to column names."""
        new_names = [f"{self.prefix}{col}" for col in table.column_names]
        return table.rename_columns(new_names)


def example_map_batch_pyarrow():
    """Example usage of MapBatch actor with PyArrow format."""
    # Create sample dataset
    ds = ray.data.from_items([
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ])
    
    # Create adapter for the actor
    adapter = create_adapter_for_actor(
        actor_class=ColumnRenameActor,
        actor_kwargs={"prefix": "renamed_", "exclude_columns": None},
        batch_size=2,
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    
    print("\nMapBatch (PyArrow) Example Results:")
    print(result_ds.take_all())
    return result_ds


# ========== Example 4: Dataset Actor ==========

class DatasetFilterActor(BaseRayDatasetActor):
    """Example actor that operates on entire dataset."""
    
    def __init__(self, min_value: float = 0.0, exclude_columns: list[str] | None = None):
        super().__init__(exclude_columns)
        self.min_value = min_value
    
    def _call(self, ds: Dataset) -> Dataset:
        """Filter dataset by minimum value."""
        return ds.filter(lambda row: row["value"] >= self.min_value)


def example_dataset_actor():
    """Example usage of Dataset actor."""
    # Create sample dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 5.0},
        {"id": 2, "value": 15.0},
        {"id": 3, "value": 25.0},
        {"id": 4, "value": 35.0},
    ])
    
    # Create adapter for the actor
    adapter = create_adapter_for_actor(
        actor_class=DatasetFilterActor,
        actor_kwargs={"min_value": 20.0, "exclude_columns": None},
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    
    print("\nDataset Actor Example Results:")
    print(result_ds.take_all())
    return result_ds


# ========== Example 5: GPU Actor ==========

class GPUProcessingActor(BaseRayMapBatchActor):
    """Example actor that uses GPU resources."""
    
    def __init__(self, multiplier: float = 2.0, exclude_columns: list[str] | None = None):
        super().__init__(exclude_columns)
        self.multiplier = multiplier
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Process batch with GPU (simulated here)."""
        values = batch.get("value", np.array([]))
        processed = values * self.multiplier
        return {"gpu_processed_value": processed}


def example_gpu_actor():
    """Example usage of GPU actor."""
    # Create sample dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 10.0},
        {"id": 2, "value": 20.0},
        {"id": 3, "value": 30.0},
    ])
    
    # Create adapter for the actor with GPU resources
    adapter = create_adapter_for_actor(
        actor_class=GPUProcessingActor,
        actor_kwargs={"multiplier": 3.0, "exclude_columns": None},
        batch_size=1,
        num_cpus=1,
        num_gpus=1,  # Request GPU
        concurrency=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    
    print("\nGPU Actor Example Results:")
    print(result_ds.take_all())
    return result_ds


if __name__ == "__main__":
    # Initialize Ray
    ray.init(ignore_reinit_error=True)
    
    try:
        # Run examples
        print("=" * 60)
        print("Running Actor Adapter Examples")
        print("=" * 60)
        
        example_flatmap()
        example_map_batch_numpy()
        example_map_batch_pyarrow()
        example_dataset_actor()
        
        # Uncomment if you have GPU available
        # example_gpu_actor()
        
    finally:
        ray.shutdown()

