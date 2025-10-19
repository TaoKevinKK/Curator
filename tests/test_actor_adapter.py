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
Unit tests for the actor adapter layer.
"""

import pytest
import numpy as np
import pyarrow as pa
from pyarrow import Table
import ray
from typing import Any

from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
    BaseRayMapBatchPyarrowActor,
    BaseRayDatasetActor,
)
from nemo_curator.backends.experimental.ray_data.actor_adapter import (
    create_adapter_for_actor,
    FlatMapActorAdapter,
    MapBatchActorAdapter,
    MapBatchPyarrowActorAdapter,
    DatasetActorAdapter,
)


@pytest.fixture(scope="module")
def ray_context():
    """Initialize Ray for tests."""
    ray.init(ignore_reinit_error=True, num_cpus=4)
    yield
    ray.shutdown()


# ========== Test Actors ==========

class TestFlatMapActor(BaseRayFlatMapActor):
    """Test actor for flat_map operations."""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        value = row.get("value", 0)
        # Split each value into two rows
        return [
            {"output": value * 2},
            {"output": value * 3},
        ]


class TestMapBatchActor(BaseRayMapBatchActor):
    """Test actor for map_batch operations with numpy."""
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        values = batch.get("value", np.array([]))
        return {"doubled": values * 2}


class TestMapBatchPyarrowActor(BaseRayMapBatchPyarrowActor):
    """Test actor for map_batch operations with PyArrow."""
    
    def _call(self, table: Table) -> Table:
        # Add a new column with doubled values
        if "value" in table.column_names:
            values = table["value"].to_numpy()
            doubled = values * 2
            return table.append_column("doubled", pa.array(doubled))
        return table


class TestDatasetActor(BaseRayDatasetActor):
    """Test actor for dataset-level operations."""
    
    def __init__(self, threshold: float = 0.0, exclude_columns=None):
        super().__init__(exclude_columns)
        self.threshold = threshold
    
    def _call(self, ds) -> Any:
        return ds.filter(lambda row: row["value"] >= self.threshold)


# ========== Tests ==========

def test_create_adapter_for_flatmap_actor(ray_context):
    """Test creating adapter for FlatMap actor."""
    adapter = create_adapter_for_actor(
        actor_class=TestFlatMapActor,
        num_cpus=1,
    )
    assert isinstance(adapter, FlatMapActorAdapter)


def test_create_adapter_for_mapbatch_actor(ray_context):
    """Test creating adapter for MapBatch actor."""
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchActor,
        batch_size=10,
        num_cpus=1,
    )
    assert isinstance(adapter, MapBatchActorAdapter)


def test_create_adapter_for_mapbatch_pyarrow_actor(ray_context):
    """Test creating adapter for MapBatch PyArrow actor."""
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchPyarrowActor,
        batch_size=10,
        num_cpus=1,
    )
    assert isinstance(adapter, MapBatchPyarrowActorAdapter)


def test_create_adapter_for_dataset_actor(ray_context):
    """Test creating adapter for Dataset actor."""
    adapter = create_adapter_for_actor(
        actor_class=TestDatasetActor,
        actor_kwargs={"threshold": 5.0},
        num_cpus=1,
    )
    assert isinstance(adapter, DatasetActorAdapter)


def test_flatmap_actor_execution(ray_context):
    """Test FlatMap actor execution through adapter."""
    # Create test dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 10},
        {"id": 2, "value": 20},
    ])
    
    # Create adapter
    adapter = create_adapter_for_actor(
        actor_class=TestFlatMapActor,
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Verify results
    assert len(results) == 4  # 2 input rows -> 4 output rows
    outputs = [r["output"] for r in results]
    assert set(outputs) == {20, 30, 40, 60}  # 10*2, 10*3, 20*2, 20*3


def test_mapbatch_actor_execution(ray_context):
    """Test MapBatch actor execution through adapter."""
    # Create test dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 10},
        {"id": 2, "value": 20},
        {"id": 3, "value": 30},
    ])
    
    # Create adapter
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchActor,
        batch_size=2,
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Verify results
    assert len(results) == 3
    doubled_values = [r["doubled"] for r in results]
    assert set(doubled_values) == {20, 40, 60}


def test_mapbatch_pyarrow_actor_execution(ray_context):
    """Test MapBatch PyArrow actor execution through adapter."""
    # Create test dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 10},
        {"id": 2, "value": 20},
    ])
    
    # Create adapter
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchPyarrowActor,
        batch_size=2,
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Verify results
    assert len(results) == 2
    for r in results:
        assert "doubled" in r
        assert r["doubled"] == r["value"] * 2


def test_dataset_actor_execution(ray_context):
    """Test Dataset actor execution through adapter."""
    # Create test dataset
    ds = ray.data.from_items([
        {"id": 1, "value": 5},
        {"id": 2, "value": 15},
        {"id": 3, "value": 25},
    ])
    
    # Create adapter
    adapter = create_adapter_for_actor(
        actor_class=TestDatasetActor,
        actor_kwargs={"threshold": 10.0},
        num_cpus=1,
    )
    
    # Process dataset
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Verify results - should filter out value < 10
    assert len(results) == 2
    values = [r["value"] for r in results]
    assert all(v >= 10 for v in values)


def test_exclude_columns_flatmap(ray_context):
    """Test exclude_columns functionality in FlatMap actor."""
    
    class ExcludeColumnsActor(BaseRayFlatMapActor):
        def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
            # Original row should have excluded columns removed
            return [{"new_value": row.get("value", 0) * 2}]
    
    ds = ray.data.from_items([
        {"id": 1, "value": 10, "exclude_me": "test"},
    ])
    
    adapter = create_adapter_for_actor(
        actor_class=ExcludeColumnsActor,
        actor_kwargs={"exclude_columns": ["exclude_me"]},
        num_cpus=1,
    )
    
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Check that excluded column is not in output
    assert len(results) == 1
    assert "new_value" in results[0]


def test_actor_with_parameters(ray_context):
    """Test actor with custom parameters."""
    
    class ParameterizedActor(BaseRayMapBatchActor):
        def __init__(self, multiplier: float = 2.0, exclude_columns=None):
            super().__init__(exclude_columns)
            self.multiplier = multiplier
        
        def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
            values = batch.get("value", np.array([]))
            return {"result": values * self.multiplier}
    
    ds = ray.data.from_items([
        {"id": 1, "value": 10},
        {"id": 2, "value": 20},
    ])
    
    adapter = create_adapter_for_actor(
        actor_class=ParameterizedActor,
        actor_kwargs={"multiplier": 5.0},
        batch_size=2,
        num_cpus=1,
    )
    
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # Verify custom multiplier was used
    assert len(results) == 2
    assert results[0]["result"] == 50
    assert results[1]["result"] == 100


def test_concurrency_parameter(ray_context):
    """Test that concurrency parameter triggers actor mode."""
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchActor,
        batch_size=10,
        num_cpus=1,
        concurrency=2,
    )
    
    # Verify adapter was created with concurrency
    assert adapter.concurrency == 2


def test_invalid_actor_class():
    """Test that invalid actor class raises error."""
    
    class InvalidActor:
        """Not a BaseRayActor subclass."""
        pass
    
    with pytest.raises(ValueError, match="must be a subclass"):
        create_adapter_for_actor(
            actor_class=InvalidActor,
            num_cpus=1,
        )


def test_adapter_resource_kwargs():
    """Test resource kwargs are properly set."""
    adapter = create_adapter_for_actor(
        actor_class=TestMapBatchActor,
        batch_size=10,
        num_cpus=2.0,
        num_gpus=0.5,
        concurrency=(1, 4),
    )
    
    compute_kwargs = adapter._get_compute_kwargs()
    assert compute_kwargs["num_cpus"] == 2.0
    assert compute_kwargs["num_gpus"] == 0.5
    assert compute_kwargs["concurrency"] == (1, 4)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

