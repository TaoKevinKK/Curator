# Actor Adapter 快速开始指南

## 5 分钟快速上手

### 步骤 1: 导入必要的模块

```python
import ray
from ray.data import Dataset
from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
)
from nemo_curator.backends.experimental.ray_data.actor_adapter import (
    create_adapter_for_actor,
)
```

### 步骤 2: 定义你的 Actor

```python
from typing import Any

class MyTextProcessorActor(BaseRayFlatMapActor):
    """处理文本数据的 Actor"""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """将文本分割成单词"""
        text = row.get("text", "")
        words = text.split()
        return [{"word": word, "count": 1} for word in words]
```

### 步骤 3: 创建适配器并处理数据

```python
# 初始化 Ray
ray.init()

# 创建测试数据
dataset = ray.data.from_items([
    {"id": 1, "text": "hello world"},
    {"id": 2, "text": "ray data processing"},
])

# 创建适配器
adapter = create_adapter_for_actor(
    actor_class=MyTextProcessorActor,
    num_cpus=1,
    concurrency=2,  # 使用 2 个并行 actors
)

# 处理数据
result = adapter.process_dataset(dataset)

# 查看结果
print(result.take_all())

# 清理
ray.shutdown()
```

## 常见使用模式

### 模式 1: 行级转换（一对一）

```python
class RowTransformActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        # 转换单行，返回一行
        return [{
            "original": row["value"],
            "transformed": row["value"] * 2,
        }]
```

### 模式 2: 行级转换（一对多）

```python
class RowExpansionActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        # 转换单行，返回多行
        items = row["items"]
        return [{"item": item, "source_id": row["id"]} for item in items]
```

### 模式 3: 批处理转换

```python
import numpy as np

class BatchProcessorActor(BaseRayMapBatchActor):
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        # 处理一批数据
        values = batch["value"]
        return {
            "normalized": (values - values.mean()) / (values.std() + 1e-8)
        }

# 使用时指定 batch_size
adapter = create_adapter_for_actor(
    actor_class=BatchProcessorActor,
    batch_size=100,  # 每批 100 条
    num_cpus=2,
)
```

### 模式 4: 有状态的 Actor（如模型推理）

```python
class ModelInferenceActor(BaseRayMapBatchActor):
    def __init__(self, model_path: str, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        # 延迟加载模型（第一次调用时）
        if self.model is None:
            self.model = self._load_model(self.model_path)
        
        # 批量推理
        predictions = self.model.predict(batch["features"])
        return {"predictions": predictions}
    
    def _load_model(self, path: str):
        # 加载模型的实际代码
        import joblib
        return joblib.load(path)

# 使用 GPU 和 Actor 模式
adapter = create_adapter_for_actor(
    actor_class=ModelInferenceActor,
    actor_kwargs={"model_path": "/path/to/model.pkl"},
    batch_size=32,
    num_cpus=2,
    num_gpus=1,  # 每个 actor 1 个 GPU
    concurrency=4,  # 4 个并行 actors
)
```

## 资源配置指南

### CPU 密集型任务

```python
adapter = create_adapter_for_actor(
    actor_class=CPUIntensiveActor,
    batch_size=50,
    num_cpus=4,  # 每个任务 4 个 CPU 核心
    concurrency=None,  # 使用 Task 模式
)
```

### GPU 密集型任务

```python
adapter = create_adapter_for_actor(
    actor_class=GPUModelActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=2,
    num_gpus=1,  # 每个 actor 1 个 GPU
    concurrency=(2, 8),  # 最少 2 个，最多 8 个 actors
)
```

### 内存密集型任务

```python
adapter = create_adapter_for_actor(
    actor_class=MemoryIntensiveActor,
    batch_size=10,  # 较小的批大小
    num_cpus=1,
    concurrency=4,  # 限制并发以控制内存使用
)
```

## 排除列（Exclude Columns）

### 排除特定列

```python
class ProcessorActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        # row 中已经不包含被排除的列
        return [{"processed": process(row)}]

adapter = create_adapter_for_actor(
    actor_class=ProcessorActor,
    actor_kwargs={
        "exclude_columns": ["temp_col", "metadata"]  # 这些列会被移除
    },
)
```

### 排除所有原始列

```python
adapter = create_adapter_for_actor(
    actor_class=ProcessorActor,
    actor_kwargs={
        "exclude_columns": "*"  # 排除所有原始列
    },
)
```

## 调试技巧

### 1. 先用 Task 模式测试

```python
# Task 模式启动快，适合调试
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_cpus=1,
    concurrency=None,  # Task 模式
)
```

### 2. 打印日志

```python
class DebuggableActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        print(f"Processing row: {row}")  # 会在 Ray worker 日志中显示
        result = process(row)
        print(f"Result: {result}")
        return result
```

### 3. 处理小数据集

```python
# 先在小数据集上测试
small_dataset = dataset.limit(10)
result = adapter.process_dataset(small_dataset)
print(result.take_all())
```

### 4. 查看 Ray Dashboard

```python
# 启动 Ray 时启用 dashboard
ray.init(include_dashboard=True)
# 然后在浏览器访问 http://127.0.0.1:8265
```

## 性能优化技巧

### 1. 选择合适的批大小

```python
# CPU 操作：较大批大小
batch_size=1000

# GPU 操作：中等批大小
batch_size=64

# 内存受限：较小批大小
batch_size=16
```

### 2. 并发度调优

```python
# 查看集群资源
resources = ray.cluster_resources()
print(f"Available CPUs: {resources['CPU']}")
print(f"Available GPUs: {resources['GPU']}")

# 根据资源设置并发度
num_gpus_available = int(resources.get('GPU', 0))
concurrency = num_gpus_available if num_gpus_available > 0 else 4

adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_gpus=1 if num_gpus_available > 0 else 0,
    concurrency=concurrency,
)
```

### 3. 使用 PyArrow 格式处理列式数据

```python
from pyarrow import Table
from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayMapBatchPyarrowActor,
)

class PyArrowProcessorActor(BaseRayMapBatchPyarrowActor):
    def _call(self, table: Table) -> Table:
        # 零拷贝的列操作
        return table.select(["col1", "col2"])

adapter = create_adapter_for_actor(
    actor_class=PyArrowProcessorActor,
    batch_size=10000,  # PyArrow 可以处理更大的批
)
```

## 常见错误和解决方案

### 错误 1: Actor 创建失败

```
RuntimeError: Actor creation failed
```

**解决方案**: 检查资源配置

```python
# 确保请求的资源不超过集群可用资源
ray.cluster_resources()

# 减少 num_cpus 或 num_gpus
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_cpus=1,  # 减少 CPU 请求
    num_gpus=0,  # 或者不使用 GPU
)
```

### 错误 2: 内存不足

```
OutOfMemoryError
```

**解决方案**: 减少批大小或并发度

```python
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    batch_size=10,  # 减小批大小
    concurrency=2,  # 减少并发
)
```

### 错误 3: Actor 类型错误

```
ValueError: actor_class must be a subclass of BaseRayActor
```

**解决方案**: 确保继承正确的基类

```python
# ❌ 错误
class MyActor:
    pass

# ✅ 正确
class MyActor(BaseRayFlatMapActor):
    def _call(self, row):
        return [row]
```

## 完整示例：端到端文本处理

```python
import ray
from typing import Any
import numpy as np
from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
)
from nemo_curator.backends.experimental.ray_data.actor_adapter import (
    create_adapter_for_actor,
)

# 1. 定义分词 Actor
class TokenizerActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text = row.get("text", "")
        tokens = text.lower().split()
        return [{"token": token, "doc_id": row["id"]} for token in tokens]

# 2. 定义特征提取 Actor
class FeatureExtractorActor(BaseRayMapBatchActor):
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        tokens = batch["token"]
        # 简单的特征：token 长度
        features = np.array([len(str(t)) for t in tokens])
        return {"token_length": features}

# 初始化 Ray
ray.init(ignore_reinit_error=True)

try:
    # 创建输入数据
    input_data = ray.data.from_items([
        {"id": 1, "text": "Hello world"},
        {"id": 2, "text": "Ray Data processing is powerful"},
        {"id": 3, "text": "Building scalable pipelines"},
    ])
    
    # 创建第一个适配器：分词
    tokenizer_adapter = create_adapter_for_actor(
        actor_class=TokenizerActor,
        num_cpus=1,
        concurrency=2,
    )
    
    # 执行分词
    tokens_ds = tokenizer_adapter.process_dataset(input_data)
    print("\n=== Tokens ===")
    print(tokens_ds.take(5))
    
    # 创建第二个适配器：特征提取
    feature_adapter = create_adapter_for_actor(
        actor_class=FeatureExtractorActor,
        batch_size=10,
        num_cpus=1,
    )
    
    # 执行特征提取
    features_ds = feature_adapter.process_dataset(tokens_ds)
    print("\n=== Features ===")
    print(features_ds.take(5))
    
    # 聚合统计
    print("\n=== Statistics ===")
    print(f"Total tokens: {features_ds.count()}")
    
finally:
    ray.shutdown()
```

## 下一步

- 📖 阅读 [ACTOR_ADAPTER_README.md](./ACTOR_ADAPTER_README.md) 了解详细设计
- 🔍 查看 [actor_adapter_example.py](./actor_adapter_example.py) 获取更多示例
- 📊 阅读 [ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md) 了解与 adapter.py 的对比
- 🧪 运行 [test_actor_adapter.py](../../../tests/test_actor_adapter.py) 查看单元测试

## 获取帮助

如果遇到问题：

1. 检查 Ray Dashboard: `http://127.0.0.1:8265`
2. 查看 Ray 日志
3. 在小数据集上测试
4. 参考示例代码

Happy coding! 🚀

