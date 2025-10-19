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
将 Ray Data 的 read_json 改为 XennaActorStageAdapter 执行

演示如何：
1. 创建 JSON Reader Actor
2. 包装为 Xenna Stage
3. 在 Pipeline 中使用

运行要求:
    pip install ray cosmos-xenna
"""

import json
import tempfile
import os
from typing import Any
from dataclasses import dataclass

import ray
from cosmos_xenna.pipelines import v1 as pipelines_v1

from nemo_curator.backends.experimental.ray_data.base_actors import BaseRayFlatMapActor
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from nemo_curator.tasks import Task


# ==================== 定义 Task 类型 ====================

@dataclass
class SimpleTask:
    """简单的 Task 实现"""
    id: int
    text: str
    
    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text}
    
    @classmethod
    def from_dict(cls, d: dict) -> "SimpleTask":
        return cls(id=d.get("id", 0), text=d.get("text", ""))


@dataclass
class FilePathTask:
    """文件路径 Task，用于触发文件读取"""
    file_path: str
    
    def to_dict(self) -> dict:
        return {"file_path": self.file_path}


# ==================== JSON Reader Actor ====================

class JsonReaderActor(BaseRayFlatMapActor):
    """
    JSON 文件读取 Actor
    
    输入：包含文件路径的 Task
    输出：文件中的每一行作为一个 Task
    """
    
    def __init__(self, exclude_columns=None):
        super().__init__(exclude_columns)
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """
        读取 JSON 文件并返回所有行
        
        Args:
            row: 包含 'file_path' 的字典
            
        Returns:
            文件中每行数据的列表
        """
        file_path = row.get("file_path")
        
        if not file_path or not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            return []
        
        results = []
        
        # 读取 JSONL 文件（每行一个 JSON 对象）
        if file_path.endswith('.jsonl'):
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        results.append(data)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Failed to parse line {line_num}: {e}")
        
        # 读取标准 JSON 文件（整个文件是一个 JSON 数组）
        elif file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # 如果是列表，展开
                    if isinstance(data, list):
                        results = data
                    else:
                        results = [data]
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse JSON file: {e}")
        
        print(f"Read {len(results)} items from {file_path}")
        return results


# ==================== 批量 JSON Reader Actor ====================

class BatchJsonReaderActor(BaseRayFlatMapActor):
    """
    批量读取多个 JSON 文件的 Actor
    
    可以处理多个文件路径，返回所有文件的内容
    """
    
    def __init__(self, max_lines_per_file: int = None, exclude_columns=None):
        super().__init__(exclude_columns)
        self.max_lines_per_file = max_lines_per_file
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """读取文件并返回指定数量的行"""
        file_path = row.get("file_path")
        
        if not file_path or not os.path.exists(file_path):
            return []
        
        results = []
        count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    # 添加源文件信息
                    data['_source_file'] = file_path
                    results.append(data)
                    
                    count += 1
                    if self.max_lines_per_file and count >= self.max_lines_per_file:
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        return results


# ==================== 示例 1: 基本用法 ====================

def example_1_basic_json_reader():
    """基本示例：读取 JSON 文件"""
    print("\n" + "="*60)
    print("示例 1: 基本 JSON Reader Stage")
    print("="*60)
    
    # 1. 创建测试 JSON 文件
    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "data.jsonl")
        
        # 写入测试数据
        with open(json_file, 'w') as f:
            for i in range(1, 6):
                data = {"id": i, "text": f"Document {i}", "value": i * 100}
                f.write(json.dumps(data) + '\n')
        
        print(f"\n创建测试文件: {json_file}")
        
        # 2. 创建 JSON Reader Stage
        reader_stage = create_xenna_actor_stage(
            actor_class=JsonReaderActor,
            num_cpus=1.0,
        )
        
        # 3. 创建输入任务（文件路径）
        input_tasks = [FilePathTask(file_path=json_file)]
        
        # 4. 创建 Pipeline
        stage_spec = pipelines_v1.StageSpec(
            stage=reader_stage,
            num_workers=1,
        )
        
        pipeline_config = pipelines_v1.PipelineConfig(
            execution_mode=pipelines_v1.ExecutionMode.STREAMING,
            logging_interval_s=10,
            return_last_stage_outputs=True,
        )
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[stage_spec],
            config=pipeline_config,
        )
        
        # 5. 执行
        print("\n执行 Pipeline...")
        results = pipelines_v1.run_pipeline(pipeline_spec)
        
        print(f"\n读取结果 ({len(results)} 条):")
        for i, result in enumerate(results[:10], 1):
            print(f"  {i}. {result}")


# ==================== 示例 2: 多文件读取 ====================

def example_2_multi_file_reader():
    """读取多个 JSON 文件"""
    print("\n" + "="*60)
    print("示例 2: 多文件 JSON Reader")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建多个文件
        files = []
        for file_idx in range(1, 4):
            json_file = os.path.join(tmpdir, f"data_{file_idx}.jsonl")
            
            with open(json_file, 'w') as f:
                for i in range(1, 4):
                    data = {
                        "id": f"{file_idx}_{i}",
                        "text": f"File {file_idx}, Doc {i}",
                        "file_num": file_idx,
                    }
                    f.write(json.dumps(data) + '\n')
            
            files.append(json_file)
        
        print(f"\n创建了 {len(files)} 个文件")
        
        # 创建 Reader Stage
        reader_stage = create_xenna_actor_stage(
            actor_class=JsonReaderActor,
            num_cpus=1.0,
        )
        
        # 为每个文件创建一个输入任务
        input_tasks = [FilePathTask(file_path=f) for f in files]
        
        print(f"\n输入任务: {len(input_tasks)} 个")
        
        # 创建 Pipeline（可以并行处理多个文件）
        stage_spec = pipelines_v1.StageSpec(
            stage=reader_stage,
            num_workers=2,  # 2 个并行 workers
        )
        
        pipeline_config = pipelines_v1.PipelineConfig(
            execution_mode=pipelines_v1.ExecutionMode.STREAMING,
            logging_interval_s=10,
            return_last_stage_outputs=True,
        )
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[stage_spec],
            config=pipeline_config,
        )
        
        # 执行
        print("\n执行 Pipeline...")
        results = pipelines_v1.run_pipeline(pipeline_spec)
        
        print(f"\n读取结果 ({len(results)} 条):")
        for result in results:
            print(f"  - {result}")


# ==================== 示例 3: Reader + Processing Pipeline ====================

class TextProcessorActor(BaseRayFlatMapActor):
    """处理文本的 Actor"""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """将文本转为大写并添加长度信息"""
        text = row.get("text", "")
        return [{
            "id": row.get("id"),
            "original_text": text,
            "processed_text": text.upper(),
            "length": len(text),
        }]


def example_3_reader_plus_processing():
    """完整 Pipeline: 读取 JSON → 处理"""
    print("\n" + "="*60)
    print("示例 3: Reader + Processing Pipeline")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        json_file = os.path.join(tmpdir, "data.jsonl")
        
        with open(json_file, 'w') as f:
            texts = [
                "The quick brown fox",
                "jumps over the lazy dog",
                "Xenna pipeline example",
            ]
            for i, text in enumerate(texts, 1):
                data = {"id": i, "text": text}
                f.write(json.dumps(data) + '\n')
        
        print(f"\n创建测试文件: {json_file}")
        
        # Stage 1: JSON Reader
        reader_stage = create_xenna_actor_stage(
            actor_class=JsonReaderActor,
            num_cpus=1.0,
        )
        
        # Stage 2: Text Processor
        processor_stage = create_xenna_actor_stage(
            actor_class=TextProcessorActor,
            num_cpus=1.0,
        )
        
        # 创建 Pipeline
        input_tasks = [FilePathTask(file_path=json_file)]
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[
                pipelines_v1.StageSpec(stage=reader_stage, num_workers=1),
                pipelines_v1.StageSpec(stage=processor_stage, num_workers=2),
            ],
            config=pipelines_v1.PipelineConfig(
                execution_mode=pipelines_v1.ExecutionMode.STREAMING,
                return_last_stage_outputs=True,
            ),
        )
        
        # 执行
        print("\n执行 Pipeline (Reader → Processor)...")
        results = pipelines_v1.run_pipeline(pipeline_spec)
        
        print(f"\n处理结果 ({len(results)} 条):")
        for result in results:
            print(f"  - ID: {result.get('id')}")
            print(f"    原文: {result.get('original_text')}")
            print(f"    处理后: {result.get('processed_text')}")
            print(f"    长度: {result.get('length')}")


# ==================== 示例 4: 使用 Ray Data 对比 ====================

def example_4_comparison_with_ray_data():
    """对比 Ray Data 和 Xenna 的方式"""
    print("\n" + "="*60)
    print("示例 4: Ray Data vs Xenna 对比")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "data.jsonl")
        
        # 创建测试数据
        with open(json_file, 'w') as f:
            for i in range(1, 6):
                data = {"id": i, "value": i * 10}
                f.write(json.dumps(data) + '\n')
        
        print(f"\n创建测试文件: {json_file}")
        
        # === 方法 A: Ray Data 原生方式 ===
        print("\n[方法 A] Ray Data 原生方式:")
        ds = ray.data.read_json(json_file)
        print(f"  读取了 {ds.count()} 行")
        print(f"  数据: {ds.take(3)}")
        
        # === 方法 B: Xenna Actor Stage 方式 ===
        print("\n[方法 B] Xenna Actor Stage 方式:")
        
        reader_stage = create_xenna_actor_stage(
            actor_class=JsonReaderActor,
            num_cpus=1.0,
        )
        
        input_tasks = [FilePathTask(file_path=json_file)]
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[pipelines_v1.StageSpec(stage=reader_stage, num_workers=1)],
            config=pipelines_v1.PipelineConfig(
                execution_mode=pipelines_v1.ExecutionMode.STREAMING,
                return_last_stage_outputs=True,
            ),
        )
        
        results = pipelines_v1.run_pipeline(pipeline_spec)
        print(f"  读取了 {len(results)} 行")
        print(f"  数据: {results[:3]}")
        
        print("\n对比:")
        print("  Ray Data: 简单直接，适合数据分析")
        print("  Xenna Stage: 可以集成到复杂 Pipeline，支持高级资源管理")


# ==================== 示例 5: 限制读取行数 ====================

def example_5_limited_reader():
    """限制每个文件读取的行数"""
    print("\n" + "="*60)
    print("示例 5: 限制读取行数")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        json_file = os.path.join(tmpdir, "large_data.jsonl")
        
        # 创建大文件
        with open(json_file, 'w') as f:
            for i in range(1, 101):  # 100 行
                data = {"id": i, "text": f"Line {i}"}
                f.write(json.dumps(data) + '\n')
        
        print(f"\n创建测试文件: {json_file} (100 行)")
        
        # 创建限制读取的 Reader
        reader_stage = create_xenna_actor_stage(
            actor_class=BatchJsonReaderActor,
            actor_kwargs={"max_lines_per_file": 10},  # 只读前 10 行
            num_cpus=1.0,
        )
        
        input_tasks = [FilePathTask(file_path=json_file)]
        
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[pipelines_v1.StageSpec(stage=reader_stage, num_workers=1)],
            config=pipelines_v1.PipelineConfig(
                execution_mode=pipelines_v1.ExecutionMode.STREAMING,
                return_last_stage_outputs=True,
            ),
        )
        
        results = pipelines_v1.run_pipeline(pipeline_spec)
        
        print(f"\n只读取了 {len(results)} 行 (限制为 10)")
        for result in results[:5]:
            print(f"  - {result}")


# ==================== 通用 JSON Reader Stage 工厂函数 ====================

def create_json_reader_stage(
    file_patterns: list[str] | str | None = None,
    max_lines: int | None = None,
    num_workers: int = 1,
    num_cpus: float = 1.0,
) -> tuple[pipelines_v1.StageSpec, list]:
    """
    创建 JSON Reader Stage 的便捷函数
    
    Args:
        file_patterns: 文件路径或模式列表
        max_lines: 每个文件最多读取的行数
        num_workers: Worker 数量
        num_cpus: 每个 worker 的 CPU 数
        
    Returns:
        (StageSpec, input_tasks) 元组
    """
    # 创建 Reader Stage
    reader_stage = create_xenna_actor_stage(
        actor_class=BatchJsonReaderActor,
        actor_kwargs={"max_lines_per_file": max_lines},
        num_cpus=num_cpus,
    )
    
    # 创建 Stage Spec
    stage_spec = pipelines_v1.StageSpec(
        stage=reader_stage,
        num_workers=num_workers,
    )
    
    # 创建输入任务
    input_tasks = []
    if file_patterns:
        if isinstance(file_patterns, str):
            file_patterns = [file_patterns]
        
        for pattern in file_patterns:
            # 如果是通配符，可以用 glob 展开
            import glob
            matching_files = glob.glob(pattern)
            for file_path in matching_files:
                input_tasks.append(FilePathTask(file_path=file_path))
    
    return stage_spec, input_tasks


def example_6_factory_function():
    """使用工厂函数创建 Reader Stage"""
    print("\n" + "="*60)
    print("示例 6: 使用工厂函数")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建多个文件
        for i in range(1, 4):
            json_file = os.path.join(tmpdir, f"data_{i}.jsonl")
            with open(json_file, 'w') as f:
                for j in range(1, 4):
                    data = {"id": f"{i}_{j}", "text": f"File {i} Line {j}"}
                    f.write(json.dumps(data) + '\n')
        
        # 使用工厂函数创建 Stage
        pattern = os.path.join(tmpdir, "*.jsonl")
        reader_spec, input_tasks = create_json_reader_stage(
            file_patterns=pattern,
            max_lines=2,  # 每个文件读 2 行
            num_workers=2,
            num_cpus=1.0,
        )
        
        print(f"\n找到 {len(input_tasks)} 个文件")
        
        # 创建 Pipeline
        pipeline_spec = pipelines_v1.PipelineSpec(
            input_data=input_tasks,
            stages=[reader_spec],
            config=pipelines_v1.PipelineConfig(
                execution_mode=pipelines_v1.ExecutionMode.STREAMING,
                return_last_stage_outputs=True,
            ),
        )
        
        results = pipelines_v1.run_pipeline(pipeline_spec)
        
        print(f"\n读取结果 ({len(results)} 条):")
        for result in results:
            print(f"  - {result}")


# ==================== 主函数 ====================

def main():
    """运行所有示例"""
    print("="*60)
    print("JSON Reader as Xenna Stage 示例")
    print("="*60)
    
    # 初始化 Ray
    ray.init(
        ignore_reinit_error=True,
        runtime_env={
            "env_vars": {"RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES": "0"}
        },
    )
    
    try:
        # 运行示例
        example_1_basic_json_reader()
        example_2_multi_file_reader()
        example_3_reader_plus_processing()
        example_4_comparison_with_ray_data()
        example_5_limited_reader()
        example_6_factory_function()
        
        print("\n" + "="*60)
        print("所有示例完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        ray.shutdown()


if __name__ == "__main__":
    main()


