# Ray Dataset 生成 Task 对象指南

## 快速示例

```python
import ray
from nemo_curator.tasks import Task
from dataclasses import dataclass

# 1. 定义 Task 子类
@dataclass
class SimpleTask(Task[dict]):
    @property
    def num_items(self) -> int:
        return 1
    
    def validate(self) -> bool:
        return self.data is not None

# 2. 从 Ray Dataset 创建 Task
ds = ray.data.from_items([
    {"id": 1, "text": "Hello world"},
    {"id": 2, "text": "Ray Dataset"},
])

# 3. 使用 map 转换
def row_to_task(row: dict) -> SimpleTask:
    return SimpleTask(
        task_id=f"task_{row['id']}",
        dataset_name="my_dataset",
        data=row,
    )

tasks_ds = ds.map(row_to_task)
tasks = tasks_ds.take_all()
```

## 方法概览

| 方法 | 适用场景 | 性能 |
|------|---------|------|
| `ds.map()` | 逐行转换 | ⭐⭐⭐ |
| `ds.map_batches()` | 批量转换 | ⭐⭐⭐⭐⭐ |
| 先收集再转换 | 小数据集 | ⭐⭐ |

---

## 方法 1: 使用 `map()` 逐行转换

### 基本用法

```python
import ray

# 创建 Ray Dataset
ds = ray.data.from_items([
    {"id": 1, "text": "hello"},
    {"id": 2, "text": "world"},
])

# 定义转换函数
def row_to_task(row: dict):
    return {
        "task_id": f"task_{row['id']}",
        "dataset_name": "example",
        "text": row["text"],
    }

# 转换
result_ds = ds.map(row_to_task)
print(result_ds.take_all())
```

### 创建实际的 Task 对象

```python
from dataclasses import dataclass
from nemo_curator.tasks import Task

@dataclass
class TextTask(Task[str]):
    @property
    def num_items(self) -> int:
        return len(self.data) if self.data else 0
    
    def validate(self) -> bool:
        return isinstance(self.data, str)

# 转换函数
def row_to_task(row: dict) -> TextTask:
    return TextTask(
        task_id=f"task_{row['id']}",
        dataset_name="text_dataset",
        data=row["text"],
    )

# 使用
ds = ray.data.from_items([
    {"id": 1, "text": "The quick brown fox"},
    {"id": 2, "text": "jumps over the lazy dog"},
])

tasks_ds = ds.map(row_to_task)
tasks = tasks_ds.take_all()

for task in tasks:
    print(f"{task.task_id}: {task.data}")
```

---

## 方法 2: 使用 `map_batches()` 批量转换（推荐）

### 优势
- ✅ 更高的性能
- ✅ 适合大数据集
- ✅ 可以使用向量化操作

```python
import ray
import numpy as np

def batch_to_tasks(batch: dict) -> dict:
    """批量转换为 Task 字典"""
    tasks = []
    batch_size = len(batch["id"])
    
    for i in range(batch_size):
        task_dict = {
            "task_id": f"task_{batch['id'][i]}",
            "dataset_name": "batch_dataset",
            "text": batch["text"][i],
        }
        tasks.append(task_dict)
    
    # 返回包含 tasks 的字典
    return {"task": tasks}

# 使用
ds = ray.data.range(100).map(lambda x: {
    "id": x["id"],
    "text": f"Text {x['id']}",
})

# 批量转换（每批 10 个）
result_ds = ds.map_batches(batch_to_tasks, batch_size=10)
```

---

## 方法 3: 从 Pandas DataFrame 创建

```python
import ray
import pandas as pd

# 创建 Ray Dataset（从 Pandas）
df = pd.DataFrame({
    "id": [1, 2, 3],
    "text": ["hello", "world", "ray"],
    "value": [100, 200, 300],
})

ds = ray.data.from_pandas(df)

# 转换为 Task
def row_to_task(row: dict):
    return {
        "task_id": f"task_{row['id']}",
        "dataset_name": "pandas_dataset",
        "data": row,
    }

tasks_ds = ds.map(row_to_task)
print(tasks_ds.take_all())
```

---

## 方法 4: 从文件直接创建

### JSON/JSONL 文件

```python
import ray

# 直接读取 JSON 文件
ds = ray.data.read_json("data.jsonl")

# 转换为 Task
def row_to_task(row: dict):
    return {
        "task_id": row.get("id", "unknown"),
        "dataset_name": "file_dataset",
        "text": row.get("text", ""),
    }

tasks_ds = ds.map(row_to_task)
```

### Parquet 文件

```python
import ray

# 读取 Parquet 文件
ds = ray.data.read_parquet("data.parquet")

# 转换为 Task
tasks_ds = ds.map(lambda row: {
    "task_id": f"task_{row['id']}",
    "dataset_name": "parquet_dataset",
    "data": row,
})
```

---

## 在 Xenna 中使用

### 从 Ray Dataset 创建 input_tasks

```python
import ray
from cosmos_xenna.pipelines import v1 as pipelines_v1

# 1. 创建 Ray Dataset
ds = ray.data.from_items([
    {"id": 1, "text": "hello world"},
    {"id": 2, "text": "xenna example"},
])

# 2. 转换为字典格式（Xenna 需要的格式）
def row_to_task_dict(row: dict) -> dict:
    return {
        "task_id": f"task_{row['id']}",
        "dataset_name": "xenna_dataset",
        "text": row["text"],
        **row  # 保留原始字段
    }

task_dicts_ds = ds.map(row_to_task_dict)
task_dicts = task_dicts_ds.take_all()

# 3. 创建简单的 Task 对象（如果需要）
from dataclasses import dataclass, field

@dataclass
class XennaTask:
    """简化的 Task for Xenna"""
    id: int
    text: str
    
    def __post_init__(self):
        pass

# 转换为 Task 对象
input_tasks = [XennaTask(id=t['id'], text=t['text']) for t in task_dicts]

# 4. 在 Xenna Pipeline 中使用
# pipeline_spec = pipelines_v1.PipelineSpec(
#     input_data=input_tasks,
#     stages=[...],
#     config=...,
# )
```

---

## 反向转换：Task → Ray Dataset

### 方法 A: 保持 Task 对象

```python
import ray

# 假设已有 Task 列表
tasks = [...]  # Task 对象列表

# 直接创建 Dataset（保持 Task 对象）
ds = ray.data.from_items(tasks)
```

### 方法 B: 转换为字典

```python
# 如果 Task 有 to_dict() 方法
task_dicts = [task.to_dict() for task in tasks]
ds = ray.data.from_items(task_dicts)

# 或者使用 map
ds = ray.data.from_items(tasks)
ds_dicts = ds.map(lambda task: task.to_dict())
```

---

## 完整示例：Ray Dataset → Task → Xenna

```python
import ray
from dataclasses import dataclass
from typing import Any

# 1. 定义简单的 Task
@dataclass
class SimpleTask:
    id: int
    text: str
    
    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text}

# 2. 从 Ray Dataset 创建
ds = ray.data.from_items([
    {"id": 1, "text": "The quick brown fox"},
    {"id": 2, "text": "jumps over lazy dog"},
])

# 3. 转换为 Task
def row_to_task(row: dict) -> SimpleTask:
    return SimpleTask(id=row["id"], text=row["text"])

tasks_ds = ds.map(row_to_task)
tasks = tasks_ds.take_all()

# 4. 用于 Xenna
print(f"创建了 {len(tasks)} 个 Task:")
for task in tasks:
    print(f"  - Task {task.id}: {task.text}")

# 这些 Task 可以作为 Xenna Pipeline 的 input_data
# input_data=tasks
```

---

## 性能优化建议

### 1. 使用 `map_batches` 替代 `map`

```python
# ❌ 慢：逐行处理
ds.map(row_to_task)

# ✅ 快：批量处理
ds.map_batches(batch_to_tasks, batch_size=100)
```

### 2. 并行度调整

```python
# 增加并行度
ds = ray.data.read_json("data.jsonl", parallelism=32)
```

### 3. 避免在 map 中创建复杂对象

```python
# ❌ 慢：创建复杂 Task 对象
ds.map(lambda row: ComplexTask(**row))

# ✅ 快：只创建字典
ds.map(lambda row: {"task_id": row["id"], "data": row})
```

---

## 常见问题

### Q1: Task 必须是特定类型吗？

**A**: 不是。在示例中可以使用简单的对象或字典。只有在需要与 NeMo Curator 的其他部分集成时，才需要继承 `Task` 基类。

### Q2: 如何处理大数据集？

**A**: 使用 `map_batches()` 并设置合适的 `batch_size`：

```python
ds.map_batches(batch_to_tasks, batch_size=1000)
```

### Q3: 能否并行创建 Task？

**A**: 可以。Ray Dataset 的 `map()` 和 `map_batches()` 都是并行执行的。

---

## 总结

### 推荐工作流

```
数据源（JSON/Parquet/DB）
    ↓ (ray.data.read_*)
Ray Dataset
    ↓ (ds.map 或 ds.map_batches)
Task 对象 / 字典
    ↓
Xenna Pipeline / Ray Data Processing
```

### 选择建议

| 场景 | 推荐方法 |
|------|---------|
| 小数据集（< 1000 行） | `ds.map()` |
| 大数据集 | `ds.map_batches()` |
| 需要向量化操作 | `ds.map_batches()` |
| 简单转换 | `ds.map(lambda)` |
| 复杂逻辑 | 定义函数 + `ds.map()` |

---

## 完整可运行示例

查看: `examples/ray_dataset_to_task_example.py`

```bash
python examples/ray_dataset_to_task_example.py
```


