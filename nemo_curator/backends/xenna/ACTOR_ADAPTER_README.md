# Xenna Actor Adapter 设计文档

## 概述

Xenna Actor Adapter 是一个适配层，允许用户使用 `base_actors.py` 中定义的 Actor 抽象，但底层**直接通过 Xenna 的调度机制执行**（而不是通过 Ray Data）。

## 设计目标

1. **保持用户接口不变** - 用户继续使用 `BaseRayActor` 子类定义处理逻辑
2. **直接 Actor 调度** - 不依赖 Ray Data，直接使用 Xenna 调度 Ray Actors
3. **资源管理** - 利用 Xenna 的资源管理和 Actor 池机制
4. **Pipeline 集成** - 无缝集成到 Xenna Pipeline 系统

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│              用户层 (User Layer)                         │
│   用户定义：BaseRayActor 子类                            │
│   - BaseRayFlatMapActor                                 │
│   - BaseRayMapBatchActor                                │
│   - BaseRayMapBatchPyarrowActor                         │
│   - BaseRayDatasetActor                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│          适配层 (Xenna Actor Adapter)                    │
│   xenna/actor_adapter.py                                │
│   - XennaActorStageAdapter (基类)                       │
│   - FlatMapActorStageAdapter                            │
│   - MapBatchActorStageAdapter                           │
│   - MapBatchPyarrowActorStageAdapter                    │
│   - DatasetActorStageAdapter                            │
│   - create_xenna_actor_stage() (工厂函数)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│          Xenna Pipeline Layer                            │
│   cosmos_xenna.pipelines.v1                             │
│   - pipelines_v1.Stage (接口)                           │
│   - pipelines_v1.StageSpec                              │
│   - pipelines_v1.run_pipeline()                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│          Xenna Execution Engine                          │
│   - Ray Actor Pool 管理                                 │
│   - 资源调度和分配                                       │
│   - 分布式任务执行                                       │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. XennaActorStageAdapter (基础适配器)

将 BaseRayActor 转换为 Xenna Stage 的基类。

```python
class XennaActorStageAdapter(pipelines_v1.Stage):
    def __init__(
        self,
        actor_class: Type[BaseRayActor],
        actor_kwargs: dict[str, Any] | None = None,
        batch_size: int | None = None,
        resources: XennaResources | None = None,
    ):
        ...
    
    @property
    def required_resources(self) -> XennaResources:
        """返回资源需求"""
        
    @property
    def stage_batch_size(self) -> int:
        """返回批大小"""
        
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        """处理任务 - 由子类实现"""
```

**关键职责**：
- 实现 Xenna Stage 接口
- 管理 Actor 实例生命周期
- 配置资源需求

### 2. FlatMapActorStageAdapter (行级映射适配器)

适配 `BaseRayFlatMapActor`，处理一对多的行级转换。

```python
class FlatMapActorStageAdapter(XennaActorStageAdapter):
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        output_tasks = []
        for task in tasks:
            row = task.to_dict()
            results = self._actor_instance(row)  # 调用用户 Actor
            for result_dict in results:
                output_tasks.append(Task.from_dict(result_dict))
        return output_tasks
```

**数据流**：
```
list[Task] → list[dict] → Actor._call() → list[list[dict]] → list[Task] (flattened)
```

### 3. MapBatchActorStageAdapter (批处理适配器 - Numpy)

适配 `BaseRayMapBatchActor`，处理批量数据（Numpy 格式）。

```python
class MapBatchActorStageAdapter(XennaActorStageAdapter):
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        # 转换为 Numpy batch
        batch = self._tasks_to_numpy_batch(tasks)
        # 调用用户 Actor
        result_batch = self._actor_instance(batch)
        # 转换回 Tasks
        return self._numpy_batch_to_tasks(result_batch, tasks)
```

**数据流**：
```
list[Task] → dict[str, np.ndarray] → Actor._call() → dict[str, np.ndarray] → list[Task]
```

### 4. MapBatchPyarrowActorStageAdapter (批处理适配器 - PyArrow)

适配 `BaseRayMapBatchPyarrowActor`，处理批量数据（PyArrow 格式）。

```python
class MapBatchPyarrowActorStageAdapter(XennaActorStageAdapter):
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        # 转换为 PyArrow Table
        table = self._tasks_to_pyarrow_table(tasks)
        # 调用用户 Actor
        result_table = self._actor_instance(table)
        # 转换回 Tasks
        return self._pyarrow_table_to_tasks(result_table)
```

**数据流**：
```
list[Task] → PyArrow Table → Actor._call() → PyArrow Table → list[Task]
```

### 5. DatasetActorStageAdapter (数据集级适配器)

适配 `BaseRayDatasetActor`，处理数据集级别的操作。

```python
class DatasetActorStageAdapter(XennaActorStageAdapter):
    def process_data(self, tasks: list[Task]) -> list[Task] | None:
        # 直接传递 task 列表
        result_tasks = self._actor_instance(tasks)
        return result_tasks
```

**注意**：由于 Xenna 不使用 Ray Dataset，这个适配器将 task 列表直接传递给 Actor。

## 工厂函数

### create_xenna_actor_stage()

自动创建合适的 Xenna Stage 适配器。

```python
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
    """
    根据 actor_class 类型自动选择适配器：
    - BaseRayFlatMapActor → FlatMapActorStageAdapter
    - BaseRayMapBatchActor → MapBatchActorStageAdapter
    - BaseRayMapBatchPyarrowActor → MapBatchPyarrowActorStageAdapter
    - BaseRayDatasetActor → DatasetActorStageAdapter
    """
```

## 使用示例

### 示例 1: FlatMap Actor

```python
from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayFlatMapActor
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from cosmos_xenna.pipelines import v1 as pipelines_v1

# 1. 定义 Actor（用户代码）
class TextTokenizerActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text = row.get("text", "")
        words = text.split()
        return [{"word": word} for word in words]

# 2. 创建 Xenna Stage
tokenizer_stage = create_xenna_actor_stage(
    actor_class=TextTokenizerActor,
    num_cpus=1.0,
)

# 3. 创建并执行 Pipeline
input_tasks = [Task(id=1, text="Hello world")]

stage_spec = pipelines_v1.StageSpec(
    stage=tokenizer_stage,
    num_workers=2,
)

pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[stage_spec],
    config=pipelines_v1.PipelineConfig(
        execution_mode=pipelines_v1.ExecutionMode.STREAMING,
        return_last_stage_outputs=True,
    ),
)

results = pipelines_v1.run_pipeline(pipeline_spec)
```

### 示例 2: MapBatch Actor with GPU

```python
class GPUModelActor(BaseRayMapBatchActor):
    def __init__(self, model_path: str, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        if self.model is None:
            self.model = load_model_to_gpu(self.model_path)
        predictions = self.model.predict(batch["features"])
        return {"predictions": predictions}

# 创建 Stage（带 GPU 资源）
inference_stage = create_xenna_actor_stage(
    actor_class=GPUModelActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=2.0,
    num_gpus=1.0,  # 每个 worker 1 个 GPU
)

stage_spec = pipelines_v1.StageSpec(
    stage=inference_stage,
    num_workers=4,  # 4 个 GPU workers
)
```

### 示例 3: 多阶段 Pipeline

```python
# Stage 1: 分词
tokenizer_stage = create_xenna_actor_stage(
    actor_class=TextTokenizerActor,
    num_cpus=1.0,
)

# Stage 2: 转大写
uppercase_stage = create_xenna_actor_stage(
    actor_class=UpperCaseActor,
    num_cpus=1.0,
)

# Stage 3: 过滤
filter_stage = create_xenna_actor_stage(
    actor_class=LengthFilterActor,
    actor_kwargs={"min_length": 4},
    num_cpus=1.0,
)

# 创建 Pipeline
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[
        pipelines_v1.StageSpec(stage=tokenizer_stage, num_workers=2),
        pipelines_v1.StageSpec(stage=uppercase_stage, num_workers=2),
        pipelines_v1.StageSpec(stage=filter_stage, num_workers=2),
    ],
    config=pipeline_config,
)

results = pipelines_v1.run_pipeline(pipeline_spec)
```

## 与 Ray Data Actor Adapter 的对比

| 特性 | Ray Data Actor Adapter | Xenna Actor Adapter |
|------|----------------------|-------------------|
| **执行引擎** | Ray Data | Xenna |
| **调度方式** | Ray Data API | Xenna Actor Pool |
| **输入格式** | Ray Dataset | list[Task] |
| **输出格式** | Ray Dataset | list[Task] |
| **资源管理** | Ray Data 自动管理 | Xenna XennaResources |
| **Actor 池** | Ray Data ActorPoolStrategy | Xenna Actor Pool |
| **批处理** | map_batches/flat_map | process_data() |
| **Pipeline 集成** | 需手动组合 | 原生支持 |
| **用户接口** | 相同（BaseRayActor） | 相同（BaseRayActor） |

## 关键区别

### 1. 数据流

**Ray Data Actor Adapter**:
```
Ray Dataset → map_batches/flat_map → Actor → Ray Dataset
```

**Xenna Actor Adapter**:
```
list[Task] → Xenna Stage → Actor → list[Task]
```

### 2. 资源配置

**Ray Data**:
```python
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_cpus=2,
    num_gpus=1,
    concurrency=4,
)
result_ds = adapter.process_dataset(input_ds)
```

**Xenna**:
```python
stage = create_xenna_actor_stage(
    actor_class=MyActor,
    num_cpus=2,
    num_gpus=1,
)
stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=4,  # 并发度
)
```

### 3. Pipeline 执行

**Ray Data**: 需要手动链接 Datasets
```python
ds1 = adapter1.process_dataset(input_ds)
ds2 = adapter2.process_dataset(ds1)
ds3 = adapter3.process_dataset(ds2)
```

**Xenna**: 原生 Pipeline 支持
```python
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[stage1_spec, stage2_spec, stage3_spec],
    config=pipeline_config,
)
results = pipelines_v1.run_pipeline(pipeline_spec)
```

## 优势

### Xenna Actor Adapter 的优势：

1. **原生 Pipeline 支持** - 无缝集成 Xenna Pipeline 系统
2. **资源管理** - 利用 Xenna 的高级资源管理（nvdecs/nvencs）
3. **Actor 池优化** - Xenna 提供更精细的 Actor 池控制
4. **监控和日志** - Xenna 提供详细的执行监控
5. **容错机制** - 支持失败重试、worker 重启等

### Ray Data Actor Adapter 的优势：

1. **Ray Data 生态** - 与 Ray Data 的其他功能无缝集成
2. **数据格式** - 直接操作 Ray Dataset
3. **自动优化** - Ray Data 的自动批处理和分区优化
4. **简单易用** - 对于简单场景更直观

## 选择指南

### 使用 Xenna Actor Adapter 当：

✅ 构建复杂的多阶段 Pipeline  
✅ 需要精细的资源管理（nvdecs/nvencs）  
✅ 需要高级容错和重试机制  
✅ 需要详细的执行监控和日志  
✅ 数据已经是 Task 格式  
✅ 与现有 Xenna Pipeline 集成  

### 使用 Ray Data Actor Adapter 当：

✅ 数据已经是 Ray Dataset 格式  
✅ 需要 Ray Data 的数据处理功能  
✅ 简单的单阶段或少量阶段处理  
✅ 快速原型和实验  
✅ 不需要复杂的 Pipeline 编排  

## 注意事项

### 1. Task 对象要求

Xenna 使用 `Task` 对象，需要确保 Task 类支持：
- `to_dict()` 方法 - 转换为字典
- `from_dict()` 方法 - 从字典创建
- 或者 `__dict__` 属性

### 2. Dataset Actor 限制

`BaseRayDatasetActor` 原本设计用于操作 Ray Dataset。在 Xenna 中，它接收 `list[Task]` 而不是 Dataset。如果需要 Dataset 功能，可能需要调整 Actor 实现。

### 3. 资源分配

确保 Xenna 集群有足够的资源（CPU/GPU/nvdecs/nvencs）来满足 Stage 的需求。

## 完整示例

查看 `actor_adapter_example.py` 获取完整的可运行示例。

## 总结

Xenna Actor Adapter 成功实现了：

1. ✅ **保持用户接口** - 用户继续使用 `base_actors.py`
2. ✅ **Xenna 执行** - 底层通过 Xenna 直接调度 Actors
3. ✅ **Pipeline 集成** - 无缝集成 Xenna Pipeline
4. ✅ **资源管理** - 支持完整的 Xenna 资源配置
5. ✅ **类型支持** - 支持所有 BaseRayActor 类型

这个设计为用户提供了一个统一的 Actor 抽象，可以根据需求选择不同的执行后端（Ray Data 或 Xenna）。

