#!/usr/bin/env python3
# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Ray Dataset 与 Task 对象互相转换示例

演示如何在 Ray Dataset 和 Task 对象之间进行转换：
1. 从 Ray Dataset 生成 Task 对象
2. 从 Task 对象生成 Ray Dataset
3. 不同类型的 Task 创建方式

运行要求:
    pip install ray pandas pyarrow
"""

import ray
import pandas as pd
import pyarrow as pa
from dataclasses import dataclass
from typing import Any

# 导入 Task 基类
from nemo_curator.tasks import Task


# ==================== 定义具体的 Task 子类 ====================

@dataclass
class SimpleTask(Task[dict]):
    """简单的 Task 实现，数据是字典"""
    
    @property
    def num_items(self) -> int:
        return 1
    
    def validate(self) -> bool:
        return self.data is not None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "dataset_name": self.dataset_name,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "SimpleTask":
        """从字典创建"""
        return cls(
            task_id=d.get("task_id", "unknown"),
            dataset_name=d.get("dataset_name", "unknown"),
            data=d.get("data", {}),
        )


@dataclass
class TextTask(Task[str]):
    """文本任务，数据是字符串"""
    
    @property
    def num_items(self) -> int:
        return len(self.data) if self.data else 0
    
    def validate(self) -> bool:
        return isinstance(self.data, str)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "dataset_name": self.dataset_name,
            "text": self.data,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "TextTask":
        """从字典创建"""
        return cls(
            task_id=d.get("task_id", "unknown"),
            dataset_name=d.get("dataset_name", "unknown"),
            data=d.get("text", ""),
        )


@dataclass
class DataFrameTask(Task[pd.DataFrame]):
    """DataFrame 任务"""
    
    @property
    def num_items(self) -> int:
        return len(self.data) if self.data is not None else 0
    
    def validate(self) -> bool:
        return isinstance(self.data, pd.DataFrame)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "dataset_name": self.dataset_name,
            "data": self.data.to_dict('records') if self.data is not None else [],
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "DataFrameTask":
        """从字典创建"""
        data_records = d.get("data", [])
        df = pd.DataFrame(data_records) if data_records else pd.DataFrame()
        return cls(
            task_id=d.get("task_id", "unknown"),
            dataset_name=d.get("dataset_name", "unknown"),
            data=df,
        )


# ==================== 方法 1: 从简单字典创建 ====================

def example_1_from_dict_items():
    """从字典数据创建 Task 对象"""
    print("\n" + "="*60)
    print("方法 1: 从字典数据创建 Task")
    print("="*60)
    
    # 1. 创建 Ray Dataset（字典格式）
    ds = ray.data.from_items([
        {"id": 1, "text": "Hello world"},
        {"id": 2, "text": "Ray Dataset example"},
        {"id": 3, "text": "Task object creation"},
    ])
    
    print("\n原始 Ray Dataset:")
    print(ds.take(3))
    
    # 2. 将 Ray Dataset 转换为 Task 对象
    def row_to_task(row: dict) -> SimpleTask:
        return SimpleTask(
            task_id=f"task_{row['id']}",
            dataset_name="example_dataset",
            data=row,
        )
    
    # 使用 map 转换
    tasks_ds = ds.map(row_to_task)
    
    # 3. 获取 Task 列表
    tasks = tasks_ds.take_all()
    
    print(f"\n生成的 Task 对象 (共 {len(tasks)} 个):")
    for task in tasks:
        print(f"  - {task}")
        print(f"    数据: {task.data}")
    
    return tasks


# ==================== 方法 2: 从文本数据创建 ====================

def example_2_from_text_data():
    """从文本数据创建 TextTask"""
    print("\n" + "="*60)
    print("方法 2: 从文本数据创建 TextTask")
    print("="*60)
    
    # 1. 创建包含文本的 Ray Dataset
    texts = [
        "The quick brown fox jumps over the lazy dog",
        "Xenna is a powerful execution engine",
        "Ray Dataset with Task objects",
    ]
    
    ds = ray.data.from_items([{"id": i, "text": text} for i, text in enumerate(texts, 1)])
    
    print("\n原始 Ray Dataset:")
    print(ds.take(3))
    
    # 2. 转换为 TextTask
    def row_to_text_task(row: dict) -> TextTask:
        return TextTask(
            task_id=f"text_task_{row['id']}",
            dataset_name="text_dataset",
            data=row["text"],
        )
    
    tasks_ds = ds.map(row_to_text_task)
    tasks = tasks_ds.take_all()
    
    print(f"\n生成的 TextTask 对象 (共 {len(tasks)} 个):")
    for task in tasks:
        print(f"  - {task}")
        print(f"    文本长度: {task.num_items} 字符")
    
    return tasks


# ==================== 方法 3: 从 Pandas DataFrame 创建 ====================

def example_3_from_dataframe():
    """从 Pandas DataFrame 创建 DataFrameTask"""
    print("\n" + "="*60)
    print("方法 3: 从 DataFrame 创建 DataFrameTask")
    print("="*60)
    
    # 1. 创建 Ray Dataset（包含多行数据）
    data_items = [
        {"group": "A", "value": 100, "category": "X"},
        {"group": "A", "value": 200, "category": "Y"},
        {"group": "B", "value": 150, "category": "X"},
        {"group": "B", "value": 250, "category": "Y"},
    ]
    
    ds = ray.data.from_items(data_items)
    
    print("\n原始 Ray Dataset:")
    print(ds.take_all())
    
    # 2. 按组聚合，创建每组的 DataFrame Task
    # 先转换为 Pandas
    df_all = ds.to_pandas()
    
    tasks = []
    for group_name, group_df in df_all.groupby("group"):
        task = DataFrameTask(
            task_id=f"group_{group_name}",
            dataset_name="grouped_dataset",
            data=group_df.reset_index(drop=True),
        )
        tasks.append(task)
    
    print(f"\n生成的 DataFrameTask 对象 (共 {len(tasks)} 个):")
    for task in tasks:
        print(f"  - {task}")
        print(f"    数据形状: {task.data.shape}")
        print(f"    数据:\n{task.data}")
    
    return tasks


# ==================== 方法 4: Task 对象转回 Ray Dataset ====================

def example_4_task_to_dataset(tasks: list[Task]):
    """将 Task 对象转换回 Ray Dataset"""
    print("\n" + "="*60)
    print("方法 4: Task 对象转回 Ray Dataset")
    print("="*60)
    
    print(f"\n输入: {len(tasks)} 个 Task 对象")
    
    # 方法 A: 直接从 Task 对象创建（保持 Task 对象）
    print("\n[A] 直接从 Task 对象创建:")
    ds_tasks = ray.data.from_items(tasks)
    print(f"Dataset 行数: {ds_tasks.count()}")
    print("前 2 个 Task:")
    print(ds_tasks.take(2))
    
    # 方法 B: 转换为字典格式
    print("\n[B] 转换为字典格式:")
    task_dicts = [task.to_dict() for task in tasks if hasattr(task, 'to_dict')]
    ds_dicts = ray.data.from_items(task_dicts)
    print(f"Dataset 行数: {ds_dicts.count()}")
    print("前 2 个字典:")
    print(ds_dicts.take(2))
    
    return ds_tasks, ds_dicts


# ==================== 方法 5: 批量转换（使用 map_batches）====================

def example_5_batch_conversion():
    """使用 map_batches 批量创建 Task"""
    print("\n" + "="*60)
    print("方法 5: 使用 map_batches 批量创建 Task")
    print("="*60)
    
    # 1. 创建较大的 Ray Dataset
    ds = ray.data.range(10).map(lambda x: {
        "id": x["id"],
        "value": x["id"] * 10,
        "text": f"Item {x['id']}",
    })
    
    print(f"\n原始 Ray Dataset (行数: {ds.count()}):")
    print(ds.take(3))
    
    # 2. 批量转换为 Task（更高效）
    def batch_to_tasks(batch: dict[str, Any]) -> dict[str, list]:
        """批量转换为 Task 对象"""
        tasks = []
        batch_size = len(batch["id"])
        
        for i in range(batch_size):
            task = SimpleTask(
                task_id=f"batch_task_{batch['id'][i]}",
                dataset_name="batch_dataset",
                data={
                    "id": batch["id"][i],
                    "value": batch["value"][i],
                    "text": batch["text"][i],
                },
            )
            tasks.append(task)
        
        # 返回包含 Task 对象的字典
        return {"task": tasks}
    
    # 使用 map_batches
    tasks_ds = ds.map_batches(batch_to_tasks, batch_size=5, batch_format="numpy")
    
    print(f"\nTask Dataset (行数: {tasks_ds.count()}):")
    sample = tasks_ds.take(3)
    for item in sample:
        task = item["task"]
        print(f"  - {task}")


# ==================== 方法 6: 从文件加载并创建 Task ====================

def example_6_from_file():
    """从文件加载数据并创建 Task"""
    print("\n" + "="*60)
    print("方法 6: 从文件加载数据并创建 Task")
    print("="*60)
    
    import tempfile
    import json
    import os
    
    # 1. 创建临时 JSON 文件
    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "data.jsonl")
        
        # 写入 JSONL 数据
        with open(json_file, 'w') as f:
            for i in range(1, 4):
                data = {"id": i, "text": f"Document {i}", "category": f"cat_{i%2}"}
                f.write(json.dumps(data) + '\n')
        
        print(f"\n创建临时文件: {json_file}")
        
        # 2. 用 Ray 读取
        ds = ray.data.read_json(json_file)
        
        print(f"Ray Dataset (行数: {ds.count()}):")
        print(ds.take(3))
        
        # 3. 转换为 Task
        def row_to_task(row: dict) -> SimpleTask:
            return SimpleTask(
                task_id=f"doc_{row['id']}",
                dataset_name="document_dataset",
                data=row,
            )
        
        tasks_ds = ds.map(row_to_task)
        tasks = tasks_ds.take_all()
        
        print(f"\n生成的 Task 对象 (共 {len(tasks)} 个):")
        for task in tasks:
            print(f"  - {task.task_id}: {task.data}")
    
    return tasks


# ==================== 方法 7: 实际使用场景 ====================

def example_7_real_world_usage():
    """实际使用场景：结合 Xenna Actor Adapter"""
    print("\n" + "="*60)
    print("方法 7: 实际使用场景")
    print("="*60)
    
    # 模拟实际场景：从 Ray Dataset 创建 Task 用于 Xenna
    
    # 1. 从数据源创建 Ray Dataset
    print("\n[1] 从数据源创建 Ray Dataset")
    ds = ray.data.from_items([
        {"id": 1, "text": "The quick brown fox jumps over lazy dog"},
        {"id": 2, "text": "Xenna is a powerful execution engine"},
        {"id": 3, "text": "Ray Dataset with Task objects"},
    ])
    
    # 2. 转换为 Task 对象（用于 Xenna）
    print("\n[2] 转换为 Task 对象")
    
    def create_text_task(row: dict) -> dict:
        """创建 TextTask 并返回其字典表示"""
        task = TextTask(
            task_id=f"task_{row['id']}",
            dataset_name="xenna_dataset",
            data=row["text"],
        )
        # 返回字典表示，包含原始数据
        return {
            "task_id": task.task_id,
            "dataset_name": task.dataset_name,
            "text": task.data,
            "id": row["id"],
        }
    
    tasks_ds = ds.map(create_text_task)
    task_dicts = tasks_ds.take_all()
    
    print(f"创建了 {len(task_dicts)} 个 Task:")
    for t in task_dicts:
        print(f"  - {t['task_id']}: {t['text'][:50]}...")
    
    # 3. 在实际使用中，这些 Task 可以传递给 Xenna Pipeline
    print("\n[3] 这些 Task 可以用于:")
    print("  - Xenna Actor Adapter 的 input_tasks")
    print("  - Xenna Pipeline 的 input_data")
    print("  - Ray Data Executor 的 initial_tasks")
    
    return task_dicts


# ==================== 辅助函数：Task 和 Dataset 互转 ====================

class TaskDatasetConverter:
    """Task 和 Ray Dataset 互相转换的工具类"""
    
    @staticmethod
    def tasks_to_dataset(tasks: list[Task]) -> ray.data.Dataset:
        """将 Task 列表转换为 Ray Dataset"""
        if not tasks:
            return ray.data.from_items([])
        
        # 如果 Task 有 to_dict 方法，使用它
        if hasattr(tasks[0], 'to_dict'):
            task_dicts = [task.to_dict() for task in tasks]
            return ray.data.from_items(task_dicts)
        else:
            # 否则直接使用 Task 对象
            return ray.data.from_items(tasks)
    
    @staticmethod
    def dataset_to_tasks(ds: ray.data.Dataset, task_class: type[Task]) -> list[Task]:
        """将 Ray Dataset 转换为 Task 列表"""
        items = ds.take_all()
        
        tasks = []
        for item in items:
            # 如果 Task 类有 from_dict 方法
            if hasattr(task_class, 'from_dict'):
                task = task_class.from_dict(item)
            else:
                # 否则尝试直接构造
                task = task_class(**item)
            tasks.append(task)
        
        return tasks
    
    @staticmethod
    def dataset_to_tasks_with_map(
        ds: ray.data.Dataset,
        task_factory: callable
    ) -> ray.data.Dataset:
        """使用自定义工厂函数转换"""
        return ds.map(task_factory)


def demonstrate_converter():
    """演示转换工具类的使用"""
    print("\n" + "="*60)
    print("转换工具类演示")
    print("="*60)
    
    converter = TaskDatasetConverter()
    
    # 创建一些 Task
    tasks = [
        SimpleTask(task_id=f"task_{i}", dataset_name="demo", data={"value": i * 10})
        for i in range(1, 4)
    ]
    
    print(f"\n原始 Tasks ({len(tasks)} 个):")
    for task in tasks:
        print(f"  - {task}")
    
    # Task → Dataset
    ds = converter.tasks_to_dataset(tasks)
    print(f"\nRay Dataset (行数: {ds.count()}):")
    print(ds.take(3))
    
    # Dataset → Task
    tasks_back = converter.dataset_to_tasks(ds, SimpleTask)
    print(f"\n转换回的 Tasks ({len(tasks_back)} 个):")
    for task in tasks_back:
        print(f"  - {task}")


# ==================== 主函数 ====================

def main():
    """运行所有示例"""
    print("="*60)
    print("Ray Dataset 与 Task 对象互相转换示例")
    print("="*60)
    
    # 初始化 Ray
    ray.init(ignore_reinit_error=True)
    
    try:
        # 运行示例
        tasks1 = example_1_from_dict_items()
        tasks2 = example_2_from_text_data()
        tasks3 = example_3_from_dataframe()
        example_4_task_to_dataset(tasks1)
        example_5_batch_conversion()
        example_6_from_file()
        example_7_real_world_usage()
        demonstrate_converter()
        
        print("\n" + "="*60)
        print("所有示例完成！")
        print("="*60)
        
    finally:
        # 清理
        ray.shutdown()


if __name__ == "__main__":
    main()


