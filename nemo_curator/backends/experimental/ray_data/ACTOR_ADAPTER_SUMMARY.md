# Actor Adapter Layer 设计总结

## 设计概述

本次设计创建了一个**适配层（Actor Adapter Layer）**，使得用户可以继续使用 `base_actors.py` 中定义的抽象基类来实现自己的处理逻辑，而底层自动通过 Ray Data 的高效 API（`map_batches`、`flat_map` 等）来执行，实现了与 `adapter.py` 类似的设计模式。

## 核心设计原则

### 1. 用户友好（User-Friendly）
- 用户只需继承 `BaseRayActor` 的子类，实现 `_call()` 方法
- 无需了解 Ray Data 的底层 API
- 简单直观的接口设计

### 2. 透明执行（Transparent Execution）
- 底层自动转换为 Ray Data 操作
- 自动选择 Actor 或 Task 执行模式
- 无缝集成到 Ray Data 生态系统

### 3. 灵活配置（Flexible Configuration）
- 显式的资源配置（CPU、GPU）
- 可控的并发度设置
- 支持多种批处理格式

### 4. 类型安全（Type Safety）
- 为不同操作类型提供专门的适配器
- 编译时类型检查
- 清晰的错误提示

## 创建的文件

### 1. 核心实现文件

#### `actor_adapter.py` (主要实现)
```
核心适配器实现，包含：
├─ BaseActorAdapter (基础适配器)
├─ FlatMapActorAdapter (行级 flat_map 适配器)
├─ MapBatchActorAdapter (批处理适配器 - Numpy)
├─ MapBatchPyarrowActorAdapter (批处理适配器 - PyArrow)
├─ DatasetActorAdapter (数据集级适配器)
└─ create_adapter_for_actor() (工厂函数)
```

**关键特性**:
- 4 种专门的适配器类型
- 自动 Actor/Task 模式选择
- 灵活的资源管理
- 支持多种数据格式（dict、numpy、pyarrow）

### 2. 文档文件

#### `ACTOR_ADAPTER_README.md` (设计文档)
- 详细的设计架构说明
- 每种适配器的使用场景
- 完整的使用示例
- 参数配置指南
- 最佳实践

#### `ARCHITECTURE_COMPARISON.md` (架构对比)
- adapter.py vs actor_adapter.py 详细对比
- 使用场景分析
- 资源管理对比
- Actor/Task 模式选择逻辑
- 性能考虑
- 组合使用示例

#### `QUICK_START.md` (快速开始)
- 5 分钟快速上手
- 常见使用模式
- 资源配置指南
- 调试技巧
- 性能优化建议
- 常见错误解决

### 3. 示例和测试

#### `actor_adapter_example.py` (示例代码)
包含 5 个完整的使用示例：
1. TextSplitterActor - FlatMap 示例
2. NormalizationActor - MapBatch (Numpy) 示例
3. ColumnRenameActor - MapBatch (PyArrow) 示例
4. DatasetFilterActor - Dataset 级别示例
5. GPUProcessingActor - GPU 使用示例

#### `tests/test_actor_adapter.py` (单元测试)
包含 13 个测试用例：
- 适配器创建测试
- 各种 Actor 类型的执行测试
- exclude_columns 功能测试
- 参数化 Actor 测试
- 资源配置测试
- 错误处理测试

## 架构设计

### 层次结构

```
┌─────────────────────────────────────────────────┐
│           用户层 (User Layer)                    │
│   用户继承 BaseRayActor 子类实现 _call()         │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│        适配层 (Adapter Layer)                    │
│   - FlatMapActorAdapter                         │
│   - MapBatchActorAdapter                        │
│   - MapBatchPyarrowActorAdapter                 │
│   - DatasetActorAdapter                         │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│      Ray Data API Layer                          │
│   - flat_map()                                   │
│   - map_batches(batch_format="numpy")           │
│   - map_batches(batch_format="pyarrow")         │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│      Ray Core (分布式执行引擎)                   │
└─────────────────────────────────────────────────┘
```

### 适配器类型

| 适配器类型 | 对应基类 | Ray Data API | 数据格式 | 使用场景 |
|-----------|---------|-------------|---------|----------|
| FlatMapActorAdapter | BaseRayFlatMapActor | flat_map | dict | 一对多行转换 |
| MapBatchActorAdapter | BaseRayMapBatchActor | map_batches | numpy | 批量数值计算 |
| MapBatchPyarrowActorAdapter | BaseRayMapBatchPyarrowActor | map_batches | pyarrow | 列式数据操作 |
| DatasetActorAdapter | BaseRayDatasetActor | 直接调用 | Dataset | 数据集级操作 |

## 关键特性

### 1. 自动模式选择

```python
use_actors = (concurrency is not None) or (num_gpus is not None)
```

- **Actor 模式**: 有状态，适合模型推理、预加载资源
- **Task 模式**: 无状态，适合简单转换、快速启动

### 2. 灵活的资源管理

```python
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_cpus=2,           # CPU 数量
    num_gpus=1,           # GPU 数量
    concurrency=(2, 8),   # 并发度范围
    batch_size=32,        # 批大小
)
```

### 3. 支持多种数据格式

- **Dict** (FlatMap): 单行字典数据
- **Numpy** (MapBatch): 批量数组数据
- **PyArrow** (MapBatchPyarrow): 列式表数据
- **Dataset** (DatasetActor): 完整数据集

### 4. Exclude Columns 支持

```python
# 排除特定列
actor_kwargs={"exclude_columns": ["temp", "metadata"]}

# 排除所有原始列
actor_kwargs={"exclude_columns": "*"}
```

## 使用示例

### 简单示例：文本分词

```python
class TokenizerActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        words = row["text"].split()
        return [{"word": w} for w in words]

adapter = create_adapter_for_actor(
    actor_class=TokenizerActor,
    num_cpus=1,
    concurrency=4,
)
result = adapter.process_dataset(input_ds)
```

### 复杂示例：GPU 模型推理

```python
class ModelInferenceActor(BaseRayMapBatchActor):
    def __init__(self, model_path: str, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        if self.model is None:
            self.model = load_model_to_gpu(self.model_path)
        return {"predictions": self.model.predict(batch["features"])}

adapter = create_adapter_for_actor(
    actor_class=ModelInferenceActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=2,
    num_gpus=1,
    concurrency=4,
)
result = adapter.process_dataset(input_ds)
```

## 与 adapter.py 的对比

| 维度 | adapter.py | actor_adapter.py |
|------|-----------|------------------|
| **抽象级别** | Stage (高层) | Actor (低层) |
| **输入类型** | ProcessingStage | BaseRayActor 子类 |
| **适用场景** | Pipeline 编排 | 单个操作实现 |
| **配置方式** | stage.resources | 显式参数 |
| **灵活性** | 结构化 | 高度灵活 |
| **学习曲线** | 较陡 | 较平缓 |

**关系**: 互补而非竞争，共同构成完整的处理框架

## 设计优势

### 1. 对用户友好
- ✅ 简单的继承接口
- ✅ 无需了解 Ray Data 内部
- ✅ 清晰的错误提示

### 2. 高性能
- ✅ 充分利用 Ray Data 优化
- ✅ 支持 Actor 池复用
- ✅ 零拷贝优化（PyArrow）

### 3. 灵活性
- ✅ 多种执行模式
- ✅ 细粒度资源控制
- ✅ 支持多种数据格式

### 4. 可扩展性
- ✅ 易于添加新的适配器类型
- ✅ 模块化设计
- ✅ 清晰的接口定义

## 使用场景

### 适合使用 actor_adapter.py 的场景：

1. **单个数据转换操作**
   - 文本清洗、分词
   - 数据格式转换
   - 特征提取

2. **快速原型开发**
   - 实验新算法
   - 测试处理逻辑
   - 性能基准测试

3. **独立的处理任务**
   - 批量模型推理
   - 数据增强
   - 质量检查

4. **需要精确资源控制**
   - GPU 密集型任务
   - 内存受限场景
   - 多租户环境

### 推荐使用 adapter.py 的场景：

1. **完整的 Pipeline 编排**
2. **多阶段数据处理**
3. **与现有 Stage 系统集成**
4. **需要 Pipeline 监控和管理**

## 性能优化建议

### 批大小调优

```python
# CPU 密集型
batch_size = 100-1000

# GPU 密集型
batch_size = 16-128

# 内存受限
batch_size = 1-32
```

### 并发度调优

```python
# 查看可用资源
resources = ray.cluster_resources()

# 根据资源设置并发
num_gpus = int(resources.get('GPU', 0))
concurrency = num_gpus if num_gpus > 0 else cpu_count
```

### 数据格式选择

```python
# 数值密集计算 → Numpy
# 列式操作 → PyArrow
# 灵活转换 → Dict (FlatMap)
```

## 测试覆盖

单元测试覆盖了以下方面：
- ✅ 所有适配器类型的创建
- ✅ 各种 Actor 的端到端执行
- ✅ 资源配置验证
- ✅ Exclude columns 功能
- ✅ 参数化 Actor
- ✅ 错误处理

## 未来改进方向

1. **自动并发计算**
   - 类似 `calculate_concurrency_for_actors_for_stage`
   - 根据集群资源自动调整

2. **Setup 钩子**
   - 统一的 `setup()` 方法支持
   - 更好的状态管理

3. **错误恢复**
   - 更完善的错误处理机制
   - 自动重试策略

4. **监控集成**
   - 与 Ray Dashboard 深度集成
   - 性能指标收集

5. **更多适配器类型**
   - Window 操作适配器
   - Groupby 操作适配器
   - Join 操作适配器

## 总结

Actor Adapter Layer 成功实现了以下目标：

1. ✅ **保持 base_actors.py 的用户接口不变**
2. ✅ **底层通过 Ray Data 高效执行**
3. ✅ **提供类似 adapter.py 的适配机制**
4. ✅ **支持灵活的资源和并发控制**
5. ✅ **完整的文档和示例**
6. ✅ **全面的单元测试**

这个设计为用户提供了一个简单、灵活、高性能的数据处理抽象层，使得他们可以专注于业务逻辑的实现，而不需要关心底层的分布式执行细节。

## 快速链接

- 📚 [详细设计文档](./ACTOR_ADAPTER_README.md)
- 🏗️ [架构对比](./ARCHITECTURE_COMPARISON.md)
- 🚀 [快速开始指南](./QUICK_START.md)
- 💻 [示例代码](./actor_adapter_example.py)
- 🧪 [单元测试](../../../tests/test_actor_adapter.py)
- 📄 [核心实现](./actor_adapter.py)

---

**设计完成日期**: 2025-10-13  
**设计目标**: 为 base_actors.py 提供 Ray Data 执行层  
**设计状态**: ✅ 完成并可用

