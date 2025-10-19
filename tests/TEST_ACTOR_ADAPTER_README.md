# Actor Adapter 测试说明

## 测试文件

- `test_actor_adapter.py` - Actor Adapter Layer 的单元测试

## 运行测试

### 运行所有测试

```bash
cd /path/to/Curator
pytest tests/test_actor_adapter.py -v
```

### 运行特定测试

```bash
# 运行单个测试
pytest tests/test_actor_adapter.py::test_flatmap_actor_execution -v

# 运行包含特定关键字的测试
pytest tests/test_actor_adapter.py -k "flatmap" -v
```

### 带覆盖率报告

```bash
pytest tests/test_actor_adapter.py --cov=nemo_curator.backends.experimental.ray_data.actor_adapter -v
```

### 带详细输出

```bash
pytest tests/test_actor_adapter.py -vv -s
```

## 测试覆盖

### 功能测试

1. **适配器创建测试**
   - `test_create_adapter_for_flatmap_actor`
   - `test_create_adapter_for_mapbatch_actor`
   - `test_create_adapter_for_mapbatch_pyarrow_actor`
   - `test_create_adapter_for_dataset_actor`

2. **执行测试**
   - `test_flatmap_actor_execution` - FlatMap 操作
   - `test_mapbatch_actor_execution` - MapBatch (Numpy) 操作
   - `test_mapbatch_pyarrow_actor_execution` - MapBatch (PyArrow) 操作
   - `test_dataset_actor_execution` - Dataset 级别操作

3. **功能特性测试**
   - `test_exclude_columns_flatmap` - 列排除功能
   - `test_actor_with_parameters` - 参数化 Actor
   - `test_concurrency_parameter` - 并发度配置

4. **资源配置测试**
   - `test_adapter_resource_kwargs` - 资源参数验证

5. **错误处理测试**
   - `test_invalid_actor_class` - 无效 Actor 类处理

## 测试数据

测试使用简单的内存数据：

```python
# FlatMap 测试数据
[
    {"id": 1, "value": 10},
    {"id": 2, "value": 20},
]

# MapBatch 测试数据
[
    {"id": 1, "value": 10},
    {"id": 2, "value": 20},
    {"id": 3, "value": 30},
]

# Dataset 测试数据
[
    {"id": 1, "value": 5},
    {"id": 2, "value": 15},
    {"id": 3, "value": 25},
]
```

## 测试 Actors

测试文件定义了以下测试 Actors：

### TestFlatMapActor
```python
class TestFlatMapActor(BaseRayFlatMapActor):
    def _call(self, row):
        value = row.get("value", 0)
        return [
            {"output": value * 2},
            {"output": value * 3},
        ]
```

### TestMapBatchActor
```python
class TestMapBatchActor(BaseRayMapBatchActor):
    def _call(self, batch):
        values = batch.get("value", np.array([]))
        return {"doubled": values * 2}
```

### TestMapBatchPyarrowActor
```python
class TestMapBatchPyarrowActor(BaseRayMapBatchPyarrowActor):
    def _call(self, table):
        if "value" in table.column_names:
            values = table["value"].to_numpy()
            doubled = values * 2
            return table.append_column("doubled", pa.array(doubled))
        return table
```

### TestDatasetActor
```python
class TestDatasetActor(BaseRayDatasetActor):
    def __init__(self, threshold: float = 0.0, exclude_columns=None):
        super().__init__(exclude_columns)
        self.threshold = threshold
    
    def _call(self, ds):
        return ds.filter(lambda row: row["value"] >= self.threshold)
```

## 测试环境

### 依赖项

- pytest
- ray
- numpy
- pyarrow

### Ray 配置

测试使用本地 Ray 集群：

```python
@pytest.fixture(scope="module")
def ray_context():
    ray.init(ignore_reinit_error=True, num_cpus=4)
    yield
    ray.shutdown()
```

## 预期结果

所有测试应该通过：

```
tests/test_actor_adapter.py::test_create_adapter_for_flatmap_actor PASSED
tests/test_actor_adapter.py::test_create_adapter_for_mapbatch_actor PASSED
tests/test_actor_adapter.py::test_create_adapter_for_mapbatch_pyarrow_actor PASSED
tests/test_actor_adapter.py::test_create_adapter_for_dataset_actor PASSED
tests/test_actor_adapter.py::test_flatmap_actor_execution PASSED
tests/test_actor_adapter.py::test_mapbatch_actor_execution PASSED
tests/test_actor_adapter.py::test_mapbatch_pyarrow_actor_execution PASSED
tests/test_actor_adapter.py::test_dataset_actor_execution PASSED
tests/test_actor_adapter.py::test_exclude_columns_flatmap PASSED
tests/test_actor_adapter.py::test_actor_with_parameters PASSED
tests/test_actor_adapter.py::test_concurrency_parameter PASSED
tests/test_actor_adapter.py::test_invalid_actor_class PASSED
tests/test_actor_adapter.py::test_adapter_resource_kwargs PASSED

===================== 13 passed in X.XXs =====================
```

## 故障排查

### Ray 未安装

```bash
pip install ray
```

### PyArrow 未安装

```bash
pip install pyarrow
```

### Ray 初始化失败

```bash
# 清理 Ray 临时文件
rm -rf /tmp/ray

# 重新运行测试
pytest tests/test_actor_adapter.py -v
```

### 测试超时

```bash
# 增加超时时间
pytest tests/test_actor_adapter.py -v --timeout=300
```

## 添加新测试

创建新测试时，遵循以下模式：

```python
def test_my_new_feature(ray_context):
    """Test description."""
    # 1. 创建测试数据
    ds = ray.data.from_items([...])
    
    # 2. 创建适配器
    adapter = create_adapter_for_actor(
        actor_class=MyTestActor,
        ...
    )
    
    # 3. 处理数据
    result_ds = adapter.process_dataset(ds)
    results = result_ds.take_all()
    
    # 4. 验证结果
    assert len(results) == expected_length
    assert results[0]["key"] == expected_value
```

## 持续集成

建议在 CI 中运行测试：

```yaml
# .github/workflows/test.yml
- name: Run Actor Adapter Tests
  run: |
    pip install -e .
    pip install pytest ray pyarrow
    pytest tests/test_actor_adapter.py -v
```

## 参考资料

- [Actor Adapter 文档](../nemo_curator/backends/experimental/ray_data/INDEX.md)
- [示例代码](../nemo_curator/backends/experimental/ray_data/actor_adapter_example.py)
- [Ray 测试文档](https://docs.ray.io/en/latest/ray-core/examples/testing-tips.html)

