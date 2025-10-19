# Xenna Actor Adapter 快速开始

## 5 分钟上手指南

### 核心概念

**Xenna Actor Adapter** 让您可以：
1. 使用 `base_actors.py` 定义 Actor（熟悉的接口）
2. 底层通过 **Xenna 直接调度执行**（不使用 Ray Data）
3. 享受 Xenna 的 Pipeline、资源管理和监控功能

## 步骤 1: 导入模块

```python
from typing import Any
from cosmos_xenna.pipelines import v1 as pipelines_v1

# 导入 Actor 基类
from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
)

# 导入 Xenna 适配器
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage

# 导入 Task
from nemo_curator.tasks import Task
```

## 步骤 2: 定义您的 Actor

```python
class TextTokenizerActor(BaseRayFlatMapActor):
    """将文本分割成单词的 Actor"""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text = row.get("text", "")
        words = text.split()
        return [{"word": word, "length": len(word)} for word in words]
```

## 步骤 3: 创建 Xenna Stage

```python
# 将 Actor 转换为 Xenna Stage
tokenizer_stage = create_xenna_actor_stage(
    actor_class=TextTokenizerActor,
    num_cpus=1.0,  # 每个 worker 的 CPU 数
)
```

## 步骤 4: 创建并执行 Pipeline

```python
import ray

# 初始化 Ray
ray.init(
    ignore_reinit_error=True,
    runtime_env={
        "env_vars": {"RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES": "0"}
    },
)

# 创建输入任务
input_tasks = [
    Task(id=1, text="Hello world"),
    Task(id=2, text="Xenna is powerful"),
]

# 创建 Stage Spec
stage_spec = pipelines_v1.StageSpec(
    stage=tokenizer_stage,
    num_workers=2,  # 2 个并行 workers
)

# 创建 Pipeline Config
pipeline_config = pipelines_v1.PipelineConfig(
    execution_mode=pipelines_v1.ExecutionMode.STREAMING,
    logging_interval_s=10,
    return_last_stage_outputs=True,
)

# 创建 Pipeline Spec
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[stage_spec],
    config=pipeline_config,
)

# 执行 Pipeline
results = pipelines_v1.run_pipeline(pipeline_spec)

print(f"输入: {len(input_tasks)} 个文档")
print(f"输出: {len(results)} 个单词")
for task in results:
    print(f"  - {task}")

ray.shutdown()
```

## 完整示例

```python
from typing import Any
import ray
from cosmos_xenna.pipelines import v1 as pipelines_v1

from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayFlatMapActor
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from nemo_curator.tasks import Task


class TextTokenizerActor(BaseRayFlatMapActor):
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        text = row.get("text", "")
        words = text.split()
        return [{"word": word} for word in words]


def main():
    # 初始化
    ray.init(
        ignore_reinit_error=True,
        runtime_env={"env_vars": {"RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES": "0"}},
    )
    
    try:
        # 创建 Stage
        stage = create_xenna_actor_stage(
            actor_class=TextTokenizerActor,
            num_cpus=1.0,
        )
        
        # 创建 Pipeline
        input_tasks = [Task(id=1, text="Hello Xenna")]
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[pipelines_v1.StageSpec(stage=stage, num_workers=2)],
            config=pipelines_v1.PipelineConfig(
                execution_mode=pipelines_v1.ExecutionMode.STREAMING,
                return_last_stage_outputs=True,
            ),
        )
        
        # 执行
        results = pipelines_v1.run_pipeline(pipeline_spec)
        print(f"Results: {results}")
        
    finally:
        ray.shutdown()


if __name__ == "__main__":
    main()
```

## 常见使用模式

### 模式 1: 批处理 Actor

```python
import numpy as np

class NormalizationActor(BaseRayMapBatchActor):
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        values = batch["value"]
        normalized = (values - values.mean()) / (values.std() + 1e-8)
        return {"normalized": normalized}

# 创建 Stage（注意 batch_size）
stage = create_xenna_actor_stage(
    actor_class=NormalizationActor,
    batch_size=32,  # 每批 32 条
    num_cpus=2.0,
)
```

### 模式 2: GPU Actor

```python
class GPUInferenceActor(BaseRayMapBatchActor):
    def __init__(self, model_path: str, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model_path = model_path
        self.model = None
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        if self.model is None:
            self.model = load_model_to_gpu(self.model_path)
        return {"predictions": self.model.predict(batch["features"])}

# 创建 Stage（带 GPU）
stage = create_xenna_actor_stage(
    actor_class=GPUInferenceActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_cpus=2.0,
    num_gpus=1.0,  # 每个 worker 1 个 GPU
)

# Stage Spec 配置 workers
stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=4,  # 4 个 GPU workers
)
```

### 模式 3: 多阶段 Pipeline

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

## 资源配置

### CPU 密集型

```python
stage = create_xenna_actor_stage(
    actor_class=CPUIntensiveActor,
    batch_size=64,
    num_cpus=4.0,  # 每个 worker 4 个 CPU
)

stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=8,  # 8 个并行 workers
)
```

### GPU 密集型

```python
stage = create_xenna_actor_stage(
    actor_class=GPUModelActor,
    batch_size=32,
    num_cpus=2.0,
    num_gpus=1.0,  # 每个 worker 1 个 GPU
)

stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=4,  # 4 个 GPU workers（需要 4 个 GPU）
)
```

### 视频处理（nvdecs/nvencs）

```python
stage = create_xenna_actor_stage(
    actor_class=VideoProcessorActor,
    num_cpus=2.0,
    num_gpus=0.5,
    nvdecs=1,  # 视频解码器
    nvencs=1,  # 视频编码器
)
```

## Pipeline 配置选项

### 执行模式

```python
# Streaming 模式（默认）
config = pipelines_v1.PipelineConfig(
    execution_mode=pipelines_v1.ExecutionMode.STREAMING,
    ...
)

# Batch 模式
config = pipelines_v1.PipelineConfig(
    execution_mode=pipelines_v1.ExecutionMode.BATCH,
    ...
)
```

### 容错配置

```python
stage_spec = pipelines_v1.StageSpec(
    stage=my_stage,
    num_workers=4,
    num_setup_attempts_python=3,  # setup 失败重试次数
    num_run_attempts_python=3,    # 执行失败重试次数
    ignore_failures=False,         # 是否忽略失败
    reset_workers_on_failure=True, # 失败后重置 workers
)
```

### 日志和监控

```python
config = pipelines_v1.PipelineConfig(
    logging_interval_s=30,  # 每 30 秒打印一次日志
    log_worker_allocation_layout=True,  # 显示 worker 分配
    ...
)
```

## 常见问题

### Q: Actor 和 Task 模式的区别？

**A**: 在 Xenna 中，所有执行都通过 Actor 池。`num_workers` 控制并发 Actor 数量。

### Q: 如何调试 Actor？

**A**: 
1. 在 Actor 的 `_call()` 方法中添加日志
2. 查看 Ray Dashboard
3. 设置较小的 `num_workers` 进行测试

### Q: Task 对象需要什么？

**A**: Task 对象需要支持：
- `to_dict()` - 转换为字典
- `from_dict()` - 从字典创建
- 或者 `__dict__` 属性

### Q: 与 Ray Data Actor Adapter 的区别？

**A**:
- **Xenna**: 直接 Actor 调度，Pipeline 集成，高级资源管理
- **Ray Data**: Ray Dataset 处理，自动优化，简单易用

选择取决于您的数据格式和需求。

## 调试技巧

### 1. 小数据集测试

```python
# 先用少量数据测试
test_tasks = input_tasks[:5]
```

### 2. 单个 Worker

```python
# 用单个 worker 调试
stage_spec = pipelines_v1.StageSpec(
    stage=stage,
    num_workers=1,
)
```

### 3. 详细日志

```python
config = pipelines_v1.PipelineConfig(
    logging_interval_s=5,  # 更频繁的日志
    ...
)
```

### 4. Ray Dashboard

访问 `http://127.0.0.1:8265` 查看：
- Actor 状态
- 资源使用
- 任务进度
- 错误日志

## 完整端到端示例

参考 `actor_adapter_example.py` 获取更多示例：
- FlatMap Actor 示例
- MapBatch Actor 示例
- GPU Actor 示例
- 多阶段 Pipeline 示例

## 下一步

- 📖 阅读 [详细文档](./ACTOR_ADAPTER_README.md)
- 💻 运行 [示例代码](./actor_adapter_example.py)
- 🔍 查看 [核心实现](./actor_adapter.py)

## 获取帮助

如果遇到问题：
1. 检查 Ray Dashboard
2. 查看 Xenna 日志
3. 参考示例代码
4. 阅读完整文档

Happy coding! 🚀

