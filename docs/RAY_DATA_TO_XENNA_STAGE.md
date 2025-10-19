# 将 Ray Data 操作转换为 Xenna Stage

## 概述

本指南展示如何将 Ray Data 的操作（如 `read_json`、`map`、`filter` 等）转换为 Xenna Stage，通过 `XennaActorStageAdapter` 执行。

## 核心思路

```
Ray Data 操作
    ↓
定义对应的 Actor (BaseRayActor 子类)
    ↓
使用 create_xenna_actor_stage() 包装
    ↓
作为 Xenna Pipeline 的 Stage
```

---

## 示例 1: read_json

### Ray Data 方式

```python
import ray

# Ray Data 原生方式
ds = ray.data.read_json("data.jsonl")
```

### Xenna Stage 方式

```python
from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayFlatMapActor
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from cosmos_xenna.pipelines import v1 as pipelines_v1

# 1. 定义 JSON Reader Actor
class JsonReaderActor(BaseRayFlatMapActor):
    def _call(self, row: dict) -> list[dict]:
        """读取文件并返回所有行"""
        import json
        
        file_path = row.get("file_path")
        results = []
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        
        return results

# 2. 创建 Xenna Stage
reader_stage = create_xenna_actor_stage(
    actor_class=JsonReaderActor,
    num_cpus=1.0,
)

# 3. 创建输入任务（文件路径）
from dataclasses import dataclass

@dataclass
class FilePathTask:
    file_path: str

input_tasks = [FilePathTask(file_path="data.jsonl")]

# 4. 在 Pipeline 中使用
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[
        pipelines_v1.StageSpec(stage=reader_stage, num_workers=1)
    ],
    config=pipelines_v1.PipelineConfig(
        execution_mode=pipelines_v1.ExecutionMode.STREAMING,
        return_last_stage_outputs=True,
    ),
)

# 5. 执行
results = pipelines_v1.run_pipeline(pipeline_spec)
```

---

## 示例 2: map 操作

### Ray Data 方式

```python
ds = ray.data.from_items([...])
ds = ds.map(lambda x: {"value": x["value"] * 2})
```

### Xenna Stage 方式

```python
# 1. 定义 Map Actor
class DoubleValueActor(BaseRayFlatMapActor):
    def _call(self, row: dict) -> list[dict]:
        """将 value 翻倍"""
        return [{"value": row["value"] * 2}]

# 2. 创建 Stage
map_stage = create_xenna_actor_stage(
    actor_class=DoubleValueActor,
    num_cpus=1.0,
)

# 3. 在 Pipeline 中使用
pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[
        pipelines_v1.StageSpec(stage=map_stage, num_workers=2)
    ],
    config=config,
)
```

---

## 示例 3: filter 操作

### Ray Data 方式

```python
ds = ds.filter(lambda x: x["value"] > 100)
```

### Xenna Stage 方式

```python
# 1. 定义 Filter Actor
class FilterActor(BaseRayFlatMapActor):
    def __init__(self, threshold: int = 100, exclude_columns=None):
        super().__init__(exclude_columns)
        self.threshold = threshold
    
    def _call(self, row: dict) -> list[dict]:
        """过滤数据"""
        if row.get("value", 0) > self.threshold:
            return [row]  # 保留
        else:
            return []  # 过滤掉

# 2. 创建 Stage（带参数）
filter_stage = create_xenna_actor_stage(
    actor_class=FilterActor,
    actor_kwargs={"threshold": 100},
    num_cpus=1.0,
)
```

---

## 示例 4: map_batches 操作

### Ray Data 方式

```python
import numpy as np

def process_batch(batch):
    return {"result": batch["value"] * 2}

ds = ds.map_batches(process_batch, batch_size=100)
```

### Xenna Stage 方式

```python
from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayMapBatchActor

# 1. 定义 Batch Actor
class BatchProcessorActor(BaseRayMapBatchActor):
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """批量处理"""
        return {"result": batch["value"] * 2}

# 2. 创建 Stage（注意 batch_size）
batch_stage = create_xenna_actor_stage(
    actor_class=BatchProcessorActor,
    batch_size=100,  # 指定批大小
    num_cpus=2.0,
)
```

---

## 示例 5: 完整 Pipeline

### Ray Data 方式

```python
# 读取 → 处理 → 过滤
ds = ray.data.read_json("data.jsonl")
ds = ds.map(lambda x: {"value": x["value"] * 2})
ds = ds.filter(lambda x: x["value"] > 100)
results = ds.take_all()
```

### Xenna Stage 方式

```python
# Stage 1: Reader
reader_stage = create_xenna_actor_stage(
    actor_class=JsonReaderActor,
    num_cpus=1.0,
)

# Stage 2: Map
map_stage = create_xenna_actor_stage(
    actor_class=DoubleValueActor,
    num_cpus=1.0,
)

# Stage 3: Filter
filter_stage = create_xenna_actor_stage(
    actor_class=FilterActor,
    actor_kwargs={"threshold": 100},
    num_cpus=1.0,
)

# 创建 Pipeline
input_tasks = [FilePathTask(file_path="data.jsonl")]

pipeline_spec = pipelines_v1.PipelineSpec(
    input_data=input_tasks,
    stages=[
        pipelines_v1.StageSpec(stage=reader_stage, num_workers=1),
        pipelines_v1.StageSpec(stage=map_stage, num_workers=2),
        pipelines_v1.StageSpec(stage=filter_stage, num_workers=2),
    ],
    config=pipelines_v1.PipelineConfig(
        execution_mode=pipelines_v1.ExecutionMode.STREAMING,
        return_last_stage_outputs=True,
    ),
)

# 执行
results = pipelines_v1.run_pipeline(pipeline_spec)
```

---

## 常见模式对照表

| Ray Data 操作 | Actor 类型 | 示例 |
|--------------|-----------|------|
| `read_json()` | `BaseRayFlatMapActor` | 读取文件，返回行列表 |
| `map()` | `BaseRayFlatMapActor` | 一对一或一对多转换 |
| `filter()` | `BaseRayFlatMapActor` | 返回 `[row]` 或 `[]` |
| `flat_map()` | `BaseRayFlatMapActor` | 返回多个结果 |
| `map_batches()` | `BaseRayMapBatchActor` | 批量处理（Numpy） |
| `map_batches()` (PyArrow) | `BaseRayMapBatchPyarrowActor` | 批量处理（PyArrow） |

---

## 工厂函数模式

为常见操作创建工厂函数：

```python
def create_json_reader_stage(
    file_patterns: list[str],
    max_lines: int | None = None,
    num_workers: int = 1,
) -> pipelines_v1.StageSpec:
    """创建 JSON Reader Stage"""
    
    reader_stage = create_xenna_actor_stage(
        actor_class=JsonReaderActor,
        actor_kwargs={"max_lines": max_lines},
        num_cpus=1.0,
    )
    
    return pipelines_v1.StageSpec(
        stage=reader_stage,
        num_workers=num_workers,
    )

def create_map_stage(
    map_fn: callable,
    num_workers: int = 2,
) -> pipelines_v1.StageSpec:
    """创建 Map Stage"""
    
    class MapActor(BaseRayFlatMapActor):
        def _call(self, row: dict) -> list[dict]:
            return [map_fn(row)]
    
    map_stage = create_xenna_actor_stage(
        actor_class=MapActor,
        num_cpus=1.0,
    )
    
    return pipelines_v1.StageSpec(
        stage=map_stage,
        num_workers=num_workers,
    )

# 使用
reader_spec = create_json_reader_stage(["data.jsonl"])
map_spec = create_map_stage(lambda x: {"value": x["value"] * 2})
```

---

## 优势对比

### Ray Data 方式
- ✅ 简单直接
- ✅ 适合数据分析
- ✅ 自动优化
- ⚠️ 资源管理有限

### Xenna Stage 方式
- ✅ 精细的资源管理（CPU/GPU/nvdecs/nvencs）
- ✅ 高级容错和重试
- ✅ 详细的监控和日志
- ✅ 支持复杂的 Pipeline 编排
- ✅ Worker 生命周期管理
- ⚠️ 需要更多代码

---

## 选择建议

| 场景 | 推荐方式 |
|------|---------|
| 快速数据分析 | Ray Data |
| 生产环境 Pipeline | Xenna Stage |
| 简单转换 | Ray Data |
| 复杂多阶段处理 | Xenna Stage |
| 需要精细资源控制 | Xenna Stage |
| GPU/视频处理 | Xenna Stage |

---

## 完整示例代码

查看: `examples/xenna_json_reader_stage.py`

```bash
python examples/xenna_json_reader_stage.py
```

包含 6 个完整示例：
1. 基本 JSON Reader
2. 多文件读取
3. Reader + Processing Pipeline
4. Ray Data vs Xenna 对比
5. 限制读取行数
6. 工厂函数使用

---

## 关键要点

1. **Actor 定义**：继承 `BaseRayFlatMapActor` 或 `BaseRayMapBatchActor`
2. **Stage 创建**：使用 `create_xenna_actor_stage()` 包装
3. **输入任务**：创建包含必要信息的 Task 对象
4. **Pipeline 集成**：作为 `StageSpec` 添加到 Pipeline

这样，您就可以将任何 Ray Data 操作转换为 Xenna Stage，享受 Xenna 的高级特性！


