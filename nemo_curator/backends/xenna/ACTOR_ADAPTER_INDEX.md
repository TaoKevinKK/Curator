# Xenna Actor Adapter 索引

## 📚 概述

欢迎使用 **Xenna Actor Adapter**！这个适配层允许您使用 `base_actors.py` 定义的 Actor 抽象，但底层**直接通过 Xenna 的调度机制执行**（而不是通过 Ray Data）。

## 🎯 核心价值

1. **统一接口** - 使用 `BaseRayActor` 定义，保持代码一致性
2. **灵活执行** - 选择 Ray Data 或 Xenna 作为执行后端
3. **直接调度** - Xenna 直接管理 Ray Actors，无需 Ray Data 中间层
4. **Pipeline 集成** - 无缝集成到 Xenna Pipeline 系统
5. **资源管理** - 利用 Xenna 的高级资源管理能力

## 📖 文档导航

### 🚀 快速开始

**推荐首选**: [QUICK_START.md](./QUICK_START.md)
- 5 分钟上手指南
- 基本使用模式
- 常见配置示例
- 调试技巧

### 📚 详细文档

[ACTOR_ADAPTER_README.md](./ACTOR_ADAPTER_README.md)
- 完整的设计说明
- 所有适配器类型详解
- 数据流转说明
- 与 Ray Data 对比
- 使用场景分析

### 📋 设计总结

[DESIGN_SUMMARY.md](./DESIGN_SUMMARY.md)
- 设计目标和原则
- 实现细节
- 文件清单
- 性能考虑
- 未来改进

### 💻 示例代码

[actor_adapter_example.py](./actor_adapter_example.py)
- 5 个完整可运行示例
- FlatMap Actor 示例
- MapBatch Actor 示例
- GPU Actor 示例
- 多阶段 Pipeline 示例

### 🔧 核心实现

[actor_adapter.py](./actor_adapter.py)
- 完整的适配器实现
- 4 种专门适配器
- 工厂函数
- 数据转换逻辑

## 🎨 架构概览

```
┌────────────────────────────────────────────┐
│   用户层：BaseRayActor 子类                 │
│   - BaseRayFlatMapActor                    │
│   - BaseRayMapBatchActor                   │
│   - BaseRayMapBatchPyarrowActor            │
│   - BaseRayDatasetActor                    │
└────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────┐
│   适配层：Xenna Actor Adapter               │
│   - XennaActorStageAdapter                 │
│   - FlatMapActorStageAdapter               │
│   - MapBatchActorStageAdapter              │
│   - MapBatchPyarrowActorStageAdapter       │
│   - DatasetActorStageAdapter               │
└────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────┐
│   Xenna Layer：pipelines_v1.Stage           │
│   - Ray Actor Pool 管理                     │
│   - 资源调度和分配                           │
│   - Pipeline 编排                           │
└────────────────────────────────────────────┘
```

## 💡 快速示例

### 最简单的例子

```python
from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayFlatMapActor
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from cosmos_xenna.pipelines import v1 as pipelines_v1
from nemo_curator.tasks import Task

# 1. 定义 Actor
class TokenizerActor(BaseRayFlatMapActor):
    def _call(self, row):
        return [{"word": w} for w in row["text"].split()]

# 2. 创建 Xenna Stage
stage = create_xenna_actor_stage(
    actor_class=TokenizerActor,
    num_cpus=1.0,
)

# 3. 执行
input_tasks = [Task(id=1, text="Hello world")]
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[pipelines_v1.StageSpec(stage=stage, num_workers=2)],
    config=pipelines_v1.PipelineConfig(
        execution_mode=pipelines_v1.ExecutionMode.STREAMING,
        return_last_stage_outputs=True,
    ),
)
results = pipelines_v1.run_pipeline(pipeline_spec)
```

### GPU 推理示例

```python
class GPUModelActor(BaseRayMapBatchActor):
    def _call(self, batch):
        return {"predictions": self.model.predict(batch["features"])}

stage = create_xenna_actor_stage(
    actor_class=GPUModelActor,
    batch_size=32,
    num_cpus=2.0,
    num_gpus=1.0,  # 每个 worker 1 个 GPU
)
```

## 🔍 组件详解

### 适配器类型

| 适配器 | 对应基类 | 数据格式 | 使用场景 |
|--------|---------|---------|----------|
| FlatMapActorStageAdapter | BaseRayFlatMapActor | dict | 一对多行转换 |
| MapBatchActorStageAdapter | BaseRayMapBatchActor | numpy | 批量数值计算 |
| MapBatchPyarrowActorStageAdapter | BaseRayMapBatchPyarrowActor | pyarrow | 列式数据操作 |
| DatasetActorStageAdapter | BaseRayDatasetActor | list[Task] | 数据集级操作 |

### 资源配置

```python
create_xenna_actor_stage(
    actor_class=MyActor,
    batch_size=32,        # 批大小
    num_cpus=2.0,         # CPU 数量
    num_gpus=1.0,         # GPU 数量
    nvdecs=1,             # 视频解码器
    nvencs=1,             # 视频编码器
    entire_gpu=False,     # 是否独占 GPU
)
```

## 📊 与 Ray Data 的对比

| 特性 | Ray Data Actor Adapter | Xenna Actor Adapter |
|------|----------------------|-------------------|
| **数据格式** | Ray Dataset | list[Task] |
| **执行引擎** | Ray Data API | Xenna Actor Pool |
| **Pipeline** | 手动链接 | 原生支持 |
| **资源管理** | 自动管理 | XennaResources |
| **监控** | Ray Dashboard | Xenna + Ray Dashboard |
| **用户接口** | 相同（BaseRayActor） | 相同（BaseRayActor） |
| **适用场景** | 数据分析、简单处理 | 复杂 Pipeline、生产环境 |

## 🎯 使用场景

### 适合使用 Xenna Actor Adapter 的场景：

✅ 复杂的多阶段 Pipeline  
✅ 需要高级资源管理（nvdecs/nvencs）  
✅ 生产环境部署  
✅ 需要容错和重试机制  
✅ 数据已经是 Task 格式  
✅ 需要详细的监控和日志  

### 适合使用 Ray Data Actor Adapter 的场景：

✅ 数据分析和探索  
✅ 数据已经是 Ray Dataset 格式  
✅ 简单的单阶段处理  
✅ 快速原型开发  
✅ 不需要复杂 Pipeline  

## 🚀 开始使用

### 方式 1: 从快速指南开始（推荐）

```bash
# 阅读快速指南
cat QUICK_START.md
```

### 方式 2: 运行示例代码

```bash
# 运行示例
python actor_adapter_example.py
```

### 方式 3: 查看详细文档

```bash
# 阅读完整文档
cat ACTOR_ADAPTER_README.md
```

## 📦 安装依赖

```bash
pip install ray
pip install pyarrow
pip install numpy
pip install cosmos-xenna  # Xenna 依赖
```

## 🔧 API 参考

### create_xenna_actor_stage()

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
    创建 Xenna Stage 从 BaseRayActor
    
    自动根据 actor_class 类型选择合适的适配器
    配置资源需求和批处理大小
    返回可用于 Xenna Pipeline 的 Stage
    """
```

## ⚙️ 配置示例

### CPU 密集型

```python
stage = create_xenna_actor_stage(
    actor_class=CPUIntensiveActor,
    batch_size=64,
    num_cpus=4.0,
)
stage_spec = pipelines_v1.StageSpec(stage=stage, num_workers=8)
```

### GPU 密集型

```python
stage = create_xenna_actor_stage(
    actor_class=GPUModelActor,
    batch_size=32,
    num_cpus=2.0,
    num_gpus=1.0,
)
stage_spec = pipelines_v1.StageSpec(stage=stage, num_workers=4)
```

### 视频处理

```python
stage = create_xenna_actor_stage(
    actor_class=VideoProcessorActor,
    num_cpus=2.0,
    num_gpus=0.5,
    nvdecs=1,
    nvencs=1,
)
```

### 多阶段 Pipeline

```python
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[
        pipelines_v1.StageSpec(stage1, num_workers=2),
        pipelines_v1.StageSpec(stage2, num_workers=4),
        pipelines_v1.StageSpec(stage3, num_workers=2),
    ],
    config=pipeline_config,
)
```

## 🐛 调试技巧

### 1. 启用详细日志

```python
config = pipelines_v1.PipelineConfig(
    logging_interval_s=5,
    log_worker_allocation_layout=True,
    ...
)
```

### 2. 使用小数据集

```python
test_tasks = input_tasks[:10]  # 先测试少量数据
```

### 3. 单 Worker 调试

```python
stage_spec = pipelines_v1.StageSpec(stage=stage, num_workers=1)
```

### 4. 查看 Ray Dashboard

访问 `http://127.0.0.1:8265` 查看：
- Actor 状态和资源使用
- 任务进度和错误
- 系统性能指标

## ❓ 常见问题

<details>
<summary><b>Q: 与 Ray Data Actor Adapter 有什么区别？</b></summary>

**A**: 
- **执行方式**: Xenna 直接调度 Actors，Ray Data 通过 map_batches/flat_map
- **数据格式**: Xenna 使用 list[Task]，Ray Data 使用 Dataset
- **Pipeline**: Xenna 原生支持，Ray Data 需要手动链接
- **适用场景**: Xenna 适合复杂 Pipeline 和生产环境，Ray Data 适合数据分析和原型

详见: [ACTOR_ADAPTER_README.md#与-ray-data-的对比](./ACTOR_ADAPTER_README.md)
</details>

<details>
<summary><b>Q: 如何选择批大小？</b></summary>

**A**: 
- CPU 操作: 50-100
- GPU 操作: 16-64
- 内存受限: 1-32

详见: [DESIGN_SUMMARY.md#批大小优化](./DESIGN_SUMMARY.md)
</details>

<details>
<summary><b>Q: 如何配置 GPU 资源？</b></summary>

**A**:
```python
stage = create_xenna_actor_stage(
    actor_class=MyGPUActor,
    num_gpus=1.0,  # 每个 worker 1 个 GPU
)
stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=4,  # 需要 4 个 GPU
)
```

详见: [QUICK_START.md#gpu-密集型](./QUICK_START.md)
</details>

<details>
<summary><b>Q: Task 对象需要什么接口？</b></summary>

**A**: Task 对象需要支持：
- `to_dict()` 方法 - 转换为字典
- `from_dict()` 方法 - 从字典创建
- 或者可访问的 `__dict__` 属性

详见: [ACTOR_ADAPTER_README.md#task-对象要求](./ACTOR_ADAPTER_README.md)
</details>

## 📝 文件清单

| 文件 | 用途 | 行数 |
|------|------|------|
| `actor_adapter.py` | 核心实现 | ~450 行 |
| `actor_adapter_example.py` | 示例代码 | ~400 行 |
| `ACTOR_ADAPTER_README.md` | 详细文档 | ~700 行 |
| `QUICK_START.md` | 快速指南 | ~400 行 |
| `DESIGN_SUMMARY.md` | 设计总结 | ~450 行 |
| `ACTOR_ADAPTER_INDEX.md` | 本文档 | ~350 行 |
| `__init__.py` | 模块导出 | ~35 行 |

**总计**: ~2,800 行代码和文档

## 🎉 设计完成

✅ **核心实现** - 4 种专门适配器 + 工厂函数  
✅ **示例代码** - 5 个完整可运行示例  
✅ **完整文档** - 详细文档、快速指南、设计总结  
✅ **模块导出** - 更新 `__init__.py`  
✅ **无 linter 错误** - 代码质量检查通过  

## 🔗 相关资源

### 内部资源

- [base_actors.py](../../experimental/ray_data/base_actors.py) - Actor 基类定义
- [adapter.py](./adapter.py) - Xenna Stage 适配器
- [executor.py](./executor.py) - Xenna 执行器

### 外部资源

- [Cosmos Xenna 文档](https://github.com/NVIDIA/cosmos-xenna)
- [Ray 文档](https://docs.ray.io/)
- [PyArrow 文档](https://arrow.apache.org/docs/python/)

## 💬 获取帮助

如果遇到问题：

1. 📖 查看文档 - 使用本索引快速定位
2. 💻 运行示例 - 参考 `actor_adapter_example.py`
3. 🔍 检查日志 - 查看 Ray Dashboard
4. 📧 联系团队 - 提交 Issue 或 PR

---

**版本**: 1.0  
**日期**: 2025-10-13  
**状态**: ✅ 完成并可用

Happy coding with Xenna Actor Adapter! 🚀

