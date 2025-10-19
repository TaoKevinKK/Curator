# Ray Data 适配层架构对比

## 整体架构视图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层 (User Layer)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐         ┌────────────────────────┐   │
│  │  ProcessingStage     │         │  BaseRayActor 子类     │   │
│  │  子类实现            │         │  (自定义 Actor)        │   │
│  │                      │         │                        │   │
│  │  - setup()           │         │  - _call()             │   │
│  │  - process_batch()   │         │  - exclude_columns     │   │
│  │  - resources         │         │                        │   │
│  └──────────────────────┘         └────────────────────────┘   │
│           ↓                                   ↓                  │
├─────────────────────────────────────────────────────────────────┤
│                      适配层 (Adapter Layer)                      │
├─────────────────────────────────────────────────────────────────┤
│           ↓                                   ↓                  │
│  ┌──────────────────────┐         ┌────────────────────────┐   │
│  │  adapter.py          │         │  actor_adapter.py      │   │
│  │                      │         │                        │   │
│  │  RayDataStageAdapter │         │  FlatMapActorAdapter   │   │
│  │  ├─ create_actor     │         │  MapBatchActorAdapter  │   │
│  │  └─ create_task      │         │  PyarrowActorAdapter   │   │
│  │                      │         │  DatasetActorAdapter   │   │
│  └──────────────────────┘         └────────────────────────┘   │
│           ↓                                   ↓                  │
├─────────────────────────────────────────────────────────────────┤
│                   Ray Data API Layer                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Ray Data Operations                                   │    │
│  │  - dataset.map_batches()                               │    │
│  │  - dataset.flat_map()                                  │    │
│  │  - ActorPoolStrategy                                   │    │
│  │  - Resource scheduling (CPUs/GPUs)                     │    │
│  └────────────────────────────────────────────────────────┘    │
│           ↓                                                      │
├─────────────────────────────────────────────────────────────────┤
│                   Ray Core (分布式执行引擎)                      │
└─────────────────────────────────────────────────────────────────┘
```

## 两种适配器的对比

### adapter.py - Stage 级别适配器

**设计目标**: 将 `ProcessingStage` 转换为 Ray Data 可执行的格式

**核心类**:
```python
RayDataStageAdapter(BaseStageAdapter)
    ↓
├─ create_actor_from_stage()  → RayDataStageActorAdapter
└─ create_task_from_stage()   → stage_map_fn()
```

**特点**:
- 📦 **高层抽象**: 处理完整的 Stage 对象
- 🔄 **Pipeline 集成**: 与 Pipeline 系统紧密集成
- 🎯 **任务导向**: 面向 Task 对象处理
- 📊 **资源管理**: 通过 `stage.resources` 管理
- 🔍 **自动推断**: 自动判断是否使用 Actor (`is_actor_stage`)

**使用场景**:
```python
# 定义 Stage
class MyStage(ProcessingStage):
    def setup(self, worker_metadata):
        self.model = load_model()
    
    def process_batch(self, tasks):
        return [self.model.process(task) for task in tasks]

# 通过 adapter 执行
adapter = RayDataStageAdapter(stage)
result_ds = adapter.process_dataset(input_ds)
```

### actor_adapter.py - Actor 级别适配器

**设计目标**: 将 `BaseRayActor` 子类转换为 Ray Data 可执行的格式

**核心类**:
```python
BaseActorAdapter
    ↓
├─ FlatMapActorAdapter        → flat_map operations
├─ MapBatchActorAdapter       → map_batches (numpy)
├─ MapBatchPyarrowActorAdapter → map_batches (pyarrow)
└─ DatasetActorAdapter        → dataset-level operations
```

**特点**:
- 🎨 **低层抽象**: 处理单个 Actor 实现
- 🔧 **灵活配置**: 显式的资源和并发配置
- 📝 **类型明确**: 为不同操作类型提供专门适配器
- 🚀 **轻量级**: 直接映射到 Ray Data API
- 🎯 **精确控制**: 细粒度的执行控制

**使用场景**:
```python
# 定义 Actor
class MyActor(BaseRayMapBatchActor):
    def _call(self, batch):
        return {"output": process(batch["input"])}

# 通过 adapter 执行
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    batch_size=32,
    num_cpus=2,
    num_gpus=1,
    concurrency=4
)
result_ds = adapter.process_dataset(input_ds)
```

## 详细对比表

| 维度 | adapter.py | actor_adapter.py |
|------|-----------|------------------|
| **抽象级别** | Stage (高层) | Actor (低层) |
| **输入类型** | ProcessingStage | BaseRayActor 子类 |
| **用户接口** | 继承 ProcessingStage | 继承 BaseRayActor |
| **数据处理** | Task 对象 | 任意数据格式 |
| **资源配置** | stage.resources | 构造函数参数 |
| **并发控制** | 自动计算 | 显式指定 |
| **批大小** | stage.batch_size | adapter 参数 |
| **Actor 判断** | is_actor_stage() | 根据 concurrency/GPU |
| **类型变体** | 单一适配器 | 4 种专门适配器 |
| **Pipeline 集成** | ✅ 紧密集成 | ⚠️ 需要手动组合 |
| **灵活性** | 结构化 | 高度灵活 |
| **学习曲线** | 较陡 | 较平缓 |
| **使用场景** | 完整 Pipeline | 单个操作/原型 |

## 使用场景对比

### 场景 1: 构建完整的数据处理 Pipeline

**推荐**: `adapter.py` (RayDataStageAdapter)

```python
# 定义多个 Stage
class DownloadStage(ProcessingStage):
    def process_batch(self, tasks):
        return [download(task) for task in tasks]

class ProcessStage(ProcessingStage):
    def setup(self, worker_metadata):
        self.model = load_model()
    
    def process_batch(self, tasks):
        return [self.model.process(task) for task in tasks]

# 构建 Pipeline
pipeline = Pipeline([
    DownloadStage(resources=Resources(cpus=1)),
    ProcessStage(resources=Resources(cpus=2, gpus=1)),
])

# 执行
backend = RayDataBackend()
backend.run_pipeline(pipeline, input_data)
```

**原因**: 
- ✅ Pipeline 系统自动处理 Stage 间的数据流转
- ✅ 统一的资源管理和调度
- ✅ 更好的错误处理和监控

### 场景 2: 实现单个数据转换操作

**推荐**: `actor_adapter.py` (Actor Adapter)

```python
# 定义简单的转换 Actor
class TextNormalizationActor(BaseRayFlatMapActor):
    def _call(self, row):
        text = row["text"].lower().strip()
        return [{"normalized_text": text}]

# 直接使用
adapter = create_adapter_for_actor(
    actor_class=TextNormalizationActor,
    num_cpus=1,
)
result_ds = adapter.process_dataset(input_ds)
```

**原因**:
- ✅ 代码更简洁直观
- ✅ 不需要 Pipeline 的额外开销
- ✅ 适合快速原型和测试

### 场景 3: GPU 模型推理

**两者都适用，取决于上下文**

**使用 adapter.py**:
```python
class ModelInferenceStage(ProcessingStage):
    def __init__(self):
        super().__init__(
            batch_size=32,
            resources=Resources(cpus=2, gpus=1)
        )
    
    def setup(self, worker_metadata):
        self.model = load_model_to_gpu()
    
    def process_batch(self, tasks):
        return [self.model.infer(task) for task in tasks]

# 作为 Pipeline 的一部分
pipeline = Pipeline([..., ModelInferenceStage(), ...])
```

**使用 actor_adapter.py**:
```python
class ModelInferenceActor(BaseRayMapBatchActor):
    def __init__(self, model_path, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    # Note: BaseRayMapBatchActor doesn't have setup() method
    # Model loading should be done in _call or __init__
    
    def _call(self, batch):
        if self.model is None:
            self.model = load_model_to_gpu(self.model_path)
        return {"predictions": self.model.infer(batch["input"])}

# 独立使用
adapter = create_adapter_for_actor(
    actor_class=ModelInferenceActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=2,
    num_gpus=1,
    concurrency=4,
)
result_ds = adapter.process_dataset(input_ds)
```

### 场景 4: 数据格式转换

**推荐**: `actor_adapter.py` (特别是 PyArrow Adapter)

```python
class SchemaTransformActor(BaseRayMapBatchPyarrowActor):
    def _call(self, table):
        # PyArrow 表操作
        return table.select(["col1", "col2"]).rename_columns(["new1", "new2"])

adapter = create_adapter_for_actor(
    actor_class=SchemaTransformActor,
    batch_size=1000,
    num_cpus=1,
)
result_ds = adapter.process_dataset(input_ds)
```

**原因**:
- ✅ 直接操作 PyArrow Table，性能更好
- ✅ 零拷贝优化
- ✅ 类型安全

## Actor/Task 模式选择

### adapter.py 的选择逻辑

```python
def is_actor_stage(stage: ProcessingStage) -> bool:
    """判断是否使用 Actor 模式"""
    # 1. 如果有 GPU，使用 Actor
    if stage.resources.gpus > 0:
        return True
    
    # 2. 如果 setup() 被重写，使用 Actor
    if stage.setup is overridden:
        return True
    
    # 3. 否则使用 Task
    return False
```

### actor_adapter.py 的选择逻辑

```python
def should_use_actors(adapter) -> bool:
    """判断是否使用 Actor 模式"""
    # 1. 如果指定了 concurrency，使用 Actor
    if adapter.concurrency is not None:
        return True
    
    # 2. 如果需要 GPU，使用 Actor
    if adapter.num_gpus is not None:
        return True
    
    # 3. 否则使用 Task
    return False
```

**对比**:
- `adapter.py`: 隐式推断，基于 Stage 特性
- `actor_adapter.py`: 显式控制，基于资源配置

## 资源管理对比

### adapter.py

```python
# 资源在 Stage 定义时指定
stage = MyStage(
    batch_size=32,
    resources=Resources(
        cpus=2,
        gpus=1,
        memory_gb=16,
    )
)

# 并发度自动计算
concurrency = calculate_concurrency_for_actors_for_stage(stage)
```

### actor_adapter.py

```python
# 资源在创建 Adapter 时指定
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    batch_size=32,
    num_cpus=2,
    num_gpus=1,
    concurrency=(2, 8),  # 显式指定范围
)
```

**优劣对比**:

| 特性 | adapter.py | actor_adapter.py |
|------|-----------|------------------|
| **配置位置** | Stage 定义 | Adapter 创建 |
| **灵活性** | 绑定到 Stage | 运行时配置 |
| **并发控制** | 自动计算 | 显式控制 |
| **可复用性** | Stage 可复用 | Actor 可复用 |
| **调试难度** | 较难（隐式） | 较易（显式） |

## 性能考虑

### 启动开销

```
Task 模式:  每次调用重新实例化
Actor 模式: 启动时实例化一次，后续复用

推荐:
- 轻量级操作 → Task 模式
- 重量级初始化（如加载模型）→ Actor 模式
```

### 并发度

```python
# adapter.py - 自动计算
# 基于集群资源和 Stage 要求

# actor_adapter.py - 手动控制
concurrency=4          # 固定 4 个 actors
concurrency=(2, 8)     # 动态 2-8 个 actors
```

### 批处理大小

```python
# 两者都支持
batch_size=32  # 每批 32 个样本

# 最佳实践:
# - CPU 操作: 较大批 (100-1000)
# - GPU 操作: 中等批 (16-128)
# - 内存受限: 较小批 (1-32)
```

## 组合使用示例

两种适配器可以在同一个项目中组合使用：

```python
# 1. 使用 Pipeline (adapter.py) 处理主流程
class MainPipeline:
    def __init__(self):
        self.pipeline = Pipeline([
            DownloadStage(),
            PreprocessStage(),
            ModelInferenceStage(),  # 使用 adapter.py
            PostprocessStage(),
        ])
    
    def run(self, data):
        return backend.run_pipeline(self.pipeline, data)


# 2. 使用 Actor Adapter (actor_adapter.py) 处理特殊操作
class DataCleaningActor(BaseRayFlatMapActor):
    def _call(self, row):
        # 复杂的数据清洗逻辑
        return clean_data(row)

# 在 Pipeline 之前做预处理
cleaning_adapter = create_adapter_for_actor(
    actor_class=DataCleaningActor,
    concurrency=8,
)
cleaned_data = cleaning_adapter.process_dataset(raw_data)

# 然后通过 Pipeline 处理
final_results = MainPipeline().run(cleaned_data)
```

## 选择指南

### 使用 adapter.py 当:

✅ 构建完整的多阶段 Pipeline  
✅ 需要 Pipeline 系统的特性（监控、错误处理等）  
✅ 处理 Task 对象  
✅ 需要与现有 Pipeline 代码集成  
✅ 偏好约定优于配置的方式  

### 使用 actor_adapter.py 当:

✅ 实现单个独立的数据转换  
✅ 需要精确控制资源和并发  
✅ 快速原型和实验  
✅ 处理非 Task 数据格式  
✅ 需要不同的批处理格式（numpy, pyarrow）  
✅ 偏好显式配置的方式  

## 未来改进方向

### actor_adapter.py 可以借鉴的特性:

1. **自动并发计算**: 类似 `calculate_concurrency_for_actors_for_stage`
2. **Setup 钩子**: 为 Actor 添加统一的 `setup()` 方法支持
3. **错误处理**: 更完善的错误恢复机制
4. **监控集成**: 与 Ray Dashboard 的更好集成

### adapter.py 可以借鉴的特性:

1. **类型专门化**: 为不同操作类型提供专门的适配器
2. **显式配置**: 提供更多显式的配置选项
3. **批处理格式**: 支持多种批处理格式（numpy, pyarrow）

## 总结

`adapter.py` 和 `actor_adapter.py` 不是竞争关系，而是互补的两层抽象：

```
高层 (Pipeline 编排) ← adapter.py
    ↕️
低层 (单操作实现) ← actor_adapter.py
```

两者共同构成了一个灵活而强大的数据处理框架，用户可以根据具体需求选择合适的抽象级别。

