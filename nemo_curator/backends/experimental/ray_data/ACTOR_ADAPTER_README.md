# Actor Adapter Layer 设计文档

## 概述

Actor Adapter Layer 是一个适配层，允许用户使用 `base_actors.py` 中定义的抽象基类来实现自己的处理逻辑，同时底层通过 Ray Data 的高效分布式执行引擎来运行，类似于 `adapter.py` 对 `ProcessingStage` 的处理方式。

## 设计目标

1. **用户友好**: 用户只需继承 `base_actors.py` 中的基类，无需关心底层执行细节
2. **透明执行**: 底层自动使用 Ray Data 的 `map_batches`/`flat_map` API 执行
3. **资源管理**: 支持灵活的 CPU/GPU 资源分配和并发控制
4. **类型安全**: 为不同的处理模式提供类型安全的抽象

## 架构设计

```
用户代码层
    ↓
base_actors.py (抽象基类)
    ↓
actor_adapter.py (适配层) ← 本次设计的核心
    ↓
Ray Data API (map_batches/flat_map)
    ↓
分布式执行
```

### 对比 adapter.py 的设计

| 特性 | adapter.py | actor_adapter.py |
|------|-----------|------------------|
| 输入抽象 | ProcessingStage | BaseRayActor 子类 |
| 处理级别 | Stage 级别 | Actor 级别 |
| 用户接口 | 定义 ProcessingStage | 继承 BaseRayActor |
| 执行方式 | 通过 RayDataStageAdapter | 通过各种 ActorAdapter |
| 资源管理 | Stage.resources | Adapter 参数 |

## 核心组件

### 1. BaseActorAdapter (基础适配器)

所有适配器的基类，提供通用的资源管理和配置接口。

```python
class BaseActorAdapter:
    def __init__(
        self,
        actor_class: Type,
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        num_cpus: float | None = None,
        num_gpus: float | None = None,
        concurrency: int | tuple[int, int] | None = None,
    ):
        ...
    
    def process_dataset(self, dataset: Dataset) -> Dataset:
        """子类必须实现的核心方法"""
        raise NotImplementedError
```

### 2. FlatMapActorAdapter (行级映射适配器)

适配 `BaseRayFlatMapActor` 子类，用于一对多的行级转换。

**使用场景**:
- 文本分词 (1 行 → N 行)
- 数据扩充
- 条件过滤生成

**特点**:
- 使用 Ray Data 的 `flat_map` API
- 支持 Actor 或 Task 模式
- 自动处理 `exclude_columns`

### 3. MapBatchActorAdapter (批处理适配器 - Numpy)

适配 `BaseRayMapBatchActor` 子类，用于批处理操作（Numpy 格式）。

**使用场景**:
- 数值计算和归一化
- 批量特征提取
- 向量化操作

**特点**:
- 使用 Ray Data 的 `map_batches` API，`batch_format="numpy"`
- 支持可配置的 `batch_size`
- 适合数值密集型计算

### 4. MapBatchPyarrowActorAdapter (批处理适配器 - PyArrow)

适配 `BaseRayMapBatchPyarrowActor` 子类，用于批处理操作（PyArrow 格式）。

**使用场景**:
- 列式数据转换
- Schema 操作
- 高效的列重命名/重组

**特点**:
- 使用 Ray Data 的 `map_batches` API，`batch_format="pyarrow"`
- 直接操作 PyArrow Table
- 零拷贝优化

### 5. DatasetActorAdapter (数据集级适配器)

适配 `BaseRayDatasetActor` 子类，用于数据集级别的操作。

**使用场景**:
- 全局过滤
- 数据集重组
- 复杂的多阶段处理

**特点**:
- 直接操作整个 Dataset
- 适合需要全局视图的操作

## 执行模式

### Actor vs Task

适配层自动根据以下规则选择执行模式：

```python
use_actors = (concurrency is not None) or (num_gpus is not None)
```

- **Actor 模式**: 
  - 有状态，支持 `setup()` 初始化
  - 适合需要预加载模型、共享状态的场景
  - GPU 操作通常使用 Actor 模式

- **Task 模式**: 
  - 无状态，每次都重新创建实例
  - 启动快，资源开销小
  - 适合简单的无状态转换

## 使用示例

### 示例 1: 文本分词器 (FlatMap)

```python
from base_actors import BaseRayFlatMapActor
from actor_adapter import create_adapter_for_actor

class TextSplitterActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text = row.get("text", "")
        words = text.split()
        return [{"word": word, "length": len(word)} for word in words]

# 创建适配器
adapter = create_adapter_for_actor(
    actor_class=TextSplitterActor,
    actor_kwargs={"exclude_columns": ["id"]},
    num_cpus=1,
    concurrency=4,  # 使用 4 个 actors
)

# 处理数据集
result_ds = adapter.process_dataset(input_ds)
```

### 示例 2: 数值归一化 (MapBatch - Numpy)

```python
from base_actors import BaseRayMapBatchActor
from actor_adapter import create_adapter_for_actor
import numpy as np

class NormalizationActor(BaseRayMapBatchActor):
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        values = batch["value"]
        normalized = (values - values.mean()) / (values.std() + 1e-8)
        return {"normalized_value": normalized}

adapter = create_adapter_for_actor(
    actor_class=NormalizationActor,
    batch_size=100,
    num_cpus=2,
)

result_ds = adapter.process_dataset(input_ds)
```

### 示例 3: GPU 模型推理 (MapBatch)

```python
from base_actors import BaseRayMapBatchActor
from actor_adapter import create_adapter_for_actor

class ModelInferenceActor(BaseRayMapBatchActor):
    def __init__(self, model_path: str, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    def setup(self):
        # 在每个 actor 上加载模型一次
        self.model = load_model(self.model_path)
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        inputs = batch["input"]
        outputs = self.model.predict(inputs)
        return {"prediction": outputs}

adapter = create_adapter_for_actor(
    actor_class=ModelInferenceActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=1,
    num_gpus=1,  # 每个 actor 使用 1 个 GPU
    concurrency=(2, 4),  # 最少 2 个，最多 4 个 actors
)

result_ds = adapter.process_dataset(input_ds)
```

### 示例 4: 数据集过滤 (Dataset Level)

```python
from base_actors import BaseRayDatasetActor
from actor_adapter import create_adapter_for_actor

class DatasetFilterActor(BaseRayDatasetActor):
    def __init__(self, threshold: float, exclude_columns=None):
        super().__init__(exclude_columns)
        self.threshold = threshold
    
    def _call(self, ds: Dataset) -> Dataset:
        return ds.filter(lambda row: row["score"] >= self.threshold)

adapter = create_adapter_for_actor(
    actor_class=DatasetFilterActor,
    actor_kwargs={"threshold": 0.8},
)

result_ds = adapter.process_dataset(input_ds)
```

## 工厂函数

为了简化使用，提供了工厂函数 `create_adapter_for_actor`，它会自动识别 actor 类型并创建相应的适配器：

```python
def create_adapter_for_actor(
    actor_class: Type,
    actor_kwargs: dict[str, Any] | None = None,
    batch_size: int | None = None,
    num_cpus: float | None = None,
    num_gpus: float | None = None,
    concurrency: int | tuple[int, int] | None = None,
) -> BaseActorAdapter:
    """自动创建合适的适配器"""
    # 根据 actor_class 的类型自动选择适配器
    if issubclass(actor_class, BaseRayFlatMapActor):
        return FlatMapActorAdapter(...)
    elif issubclass(actor_class, BaseRayMapBatchPyarrowActor):
        return MapBatchPyarrowActorAdapter(...)
    elif issubclass(actor_class, BaseRayMapBatchActor):
        return MapBatchActorAdapter(...)
    elif issubclass(actor_class, BaseRayDatasetActor):
        return DatasetActorAdapter(...)
```

## 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `actor_class` | Type | 用户定义的 actor 类 |
| `actor_kwargs` | dict | 传递给 actor 构造函数的参数 |
| `batch_size` | int | 批处理大小（仅用于 MapBatch 操作） |
| `num_cpus` | float | 每个 actor/task 的 CPU 数量 |
| `num_gpus` | float | 每个 actor/task 的 GPU 数量 |
| `concurrency` | int / tuple | Actor 池的并发度，可以是固定值或 (min, max) |

## 资源管理最佳实践

### CPU 密集型任务

```python
adapter = create_adapter_for_actor(
    actor_class=CPUIntensiveActor,
    num_cpus=4,  # 每个任务使用 4 核
    concurrency=None,  # 使用 Task 模式
)
```

### GPU 密集型任务

```python
adapter = create_adapter_for_actor(
    actor_class=GPUIntensiveActor,
    batch_size=32,
    num_cpus=2,
    num_gpus=1,  # 每个 actor 使用 1 个 GPU
    concurrency=(2, 8),  # 动态调整 actor 数量
)
```

### 混合任务

```python
adapter = create_adapter_for_actor(
    actor_class=MixedActor,
    batch_size=16,
    num_cpus=2,
    num_gpus=0.25,  # GPU 共享
    concurrency=4,
)
```

## 与 adapter.py 的对比

### 相似之处

1. **适配器模式**: 两者都使用适配器模式将用户定义的逻辑转换为 Ray Data 可执行的格式
2. **资源管理**: 都支持细粒度的 CPU/GPU 资源分配
3. **Actor/Task 选择**: 都根据配置自动选择 Actor 或 Task 模式
4. **命名约定**: 都为生成的 Actor/Task 设置有意义的名称

### 不同之处

| 特性 | adapter.py | actor_adapter.py |
|------|-----------|------------------|
| 抽象级别 | Stage (高层) | Actor (低层) |
| 适用场景 | Pipeline 编排 | 单个操作实现 |
| 配置方式 | Stage.resources | 显式参数 |
| 灵活性 | 结构化 Pipeline | 灵活组合 |
| 用户接口 | ProcessingStage | BaseRayActor 子类 |

## 运行示例

```bash
# 运行示例代码
cd /path/to/Curator
python -m nemo_curator.backends.experimental.ray_data.actor_adapter_example
```

## 总结

Actor Adapter Layer 提供了一个清晰、灵活的方式来将用户定义的处理逻辑与 Ray Data 的分布式执行引擎结合起来。它的设计特点包括：

1. **用户友好**: 简单的继承接口，无需了解 Ray Data 内部
2. **高性能**: 充分利用 Ray Data 的优化执行引擎
3. **灵活配置**: 支持多种执行模式和资源配置
4. **类型安全**: 为不同处理模式提供专门的适配器
5. **可扩展**: 易于添加新的 actor 类型和适配器

这个设计与 `adapter.py` 形成互补，共同构成了完整的处理层次结构。

