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
Xenna Actor Adapter 使用示例

这个示例展示如何使用 base_actors.py 定义的 Actor，
通过 Xenna 的调度机制执行（而不是 Ray Data）。
"""

from typing import Any
import numpy as np
from pyarrow import Table
import pyarrow as pa

from cosmos_xenna.pipelines import v1 as pipelines_v1

from nemo_curator.backends.experimental.ray_data.base_actors import (
    BaseRayFlatMapActor,
    BaseRayMapBatchActor,
    BaseRayMapBatchPyarrowActor,
)
from nemo_curator.backends.xenna.actor_adapter import create_xenna_actor_stage
from nemo_curator.backends.xenna.executor import XennaExecutor
from nemo_curator.tasks import Task


# ========== 示例 1: FlatMap Actor - 文本分词 ==========

class TextTokenizerActor(BaseRayFlatMapActor):
    """将文本分割成单词的 Actor"""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """将文本分割成多个单词"""
        text = row.get("text", "")
        doc_id = row.get("id", 0)
        words = text.lower().split()
        
        return [
            {"word": word, "doc_id": doc_id, "length": len(word)}
            for word in words
        ]


def example_flatmap_with_xenna():
    """示例：使用 Xenna 执行 FlatMap Actor"""
    print("\n" + "="*60)
    print("示例 1: FlatMap Actor - 文本分词（Xenna 执行）")
    print("="*60)
    
    # 创建 Xenna Stage（从 Actor）
    tokenizer_stage = create_xenna_actor_stage(
        actor_class=TextTokenizerActor,
        actor_kwargs={"exclude_columns": ["extra_field"]},
        batch_size=1,  # FlatMap 通常逐个处理
        num_cpus=1.0,
    )
    
    # 创建输入任务
    input_tasks = [
        Task(id=1, text="Hello world from Xenna"),
        Task(id=2, text="Ray Data with Xenna execution"),
        Task(id=3, text="Actor adapter example"),
    ]
    
    # 创建 Pipeline
    stage_spec = pipelines_v1.StageSpec(
        stage=tokenizer_stage,
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
    print(f"输入: {len(input_tasks)} 个文档")
    results = pipelines_v1.run_pipeline(pipeline_spec)
    
    print(f"\n输出: {len(results)} 个单词")
    for i, task in enumerate(results[:10]):  # 显示前 10 个结果
        print(f"  {i+1}. {task}")
    
    return results


# ========== 示例 2: MapBatch Actor - 数值归一化 ==========

class NormalizationActor(BaseRayMapBatchActor):
    """批量归一化数值的 Actor"""
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """对批量数据进行归一化"""
        values = batch.get("value", np.array([]))
        
        if len(values) > 0:
            mean = np.mean(values)
            std = np.std(values) + 1e-8
            normalized = (values - mean) / std
            
            return {
                "normalized_value": normalized,
                "original_mean": np.full(len(values), mean),
                "original_std": np.full(len(values), std),
            }
        
        return {"normalized_value": np.array([])}


def example_mapbatch_with_xenna():
    """示例：使用 Xenna 执行 MapBatch Actor"""
    print("\n" + "="*60)
    print("示例 2: MapBatch Actor - 数值归一化（Xenna 执行）")
    print("="*60)
    
    # 创建 Xenna Stage（从 Actor）
    normalization_stage = create_xenna_actor_stage(
        actor_class=NormalizationActor,
        batch_size=10,  # 每批处理 10 条
        num_cpus=2.0,
    )
    
    # 创建输入任务
    input_tasks = [
        Task(id=i, value=float(i * 10))
        for i in range(1, 21)  # 20 个任务
    ]
    
    # 创建 Pipeline
    stage_spec = pipelines_v1.StageSpec(
        stage=normalization_stage,
        num_workers=2,
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
    print(f"输入: {len(input_tasks)} 个数值")
    results = pipelines_v1.run_pipeline(pipeline_spec)
    
    print(f"\n输出: {len(results)} 个归一化结果")
    for i, task in enumerate(results[:5]):
        print(f"  {i+1}. {task}")
    
    return results


# ========== 示例 3: 多阶段 Pipeline ==========

class UpperCaseActor(BaseRayFlatMapActor):
    """将文本转换为大写的 Actor"""
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        word = row.get("word", "")
        return [{"word": word.upper(), "doc_id": row.get("doc_id")}]


class LengthFilterActor(BaseRayFlatMapActor):
    """过滤掉短单词的 Actor"""
    
    def __init__(self, min_length: int = 3, exclude_columns=None):
        super().__init__(exclude_columns)
        self.min_length = min_length
    
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        word = row.get("word", "")
        if len(word) >= self.min_length:
            return [row]
        return []  # 过滤掉


def example_multi_stage_pipeline():
    """示例：多阶段 Pipeline（Xenna 执行）"""
    print("\n" + "="*60)
    print("示例 3: 多阶段 Pipeline（Xenna 执行）")
    print("="*60)
    
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
    
    # Stage 3: 过滤短单词
    filter_stage = create_xenna_actor_stage(
        actor_class=LengthFilterActor,
        actor_kwargs={"min_length": 4},
        num_cpus=1.0,
    )
    
    # 创建输入任务
    input_tasks = [
        Task(id=1, text="The quick brown fox jumps over lazy dog"),
        Task(id=2, text="Xenna is a powerful execution engine"),
    ]
    
    # 创建 Pipeline
    stage_specs = [
        pipelines_v1.StageSpec(stage=tokenizer_stage, num_workers=2),
        pipelines_v1.StageSpec(stage=uppercase_stage, num_workers=2),
        pipelines_v1.StageSpec(stage=filter_stage, num_workers=2),
    ]
    
    pipeline_config = pipelines_v1.PipelineConfig(
        execution_mode=pipelines_v1.ExecutionMode.STREAMING,
        logging_interval_s=10,
        return_last_stage_outputs=True,
    )
    
    pipeline_spec = pipelines_v1.PipelineSpec(
        input_data=input_tasks,
        stages=stage_specs,
        config=pipeline_config,
    )
    
    # 执行
    print(f"输入: {len(input_tasks)} 个文档")
    print("Pipeline: 分词 → 转大写 → 过滤（长度 >= 4）")
    
    results = pipelines_v1.run_pipeline(pipeline_spec)
    
    print(f"\n输出: {len(results)} 个单词（长度 >= 4）")
    for i, task in enumerate(results):
        print(f"  {i+1}. {task}")
    
    return results


# ========== 示例 4: GPU Actor（模拟）==========

class GPUProcessingActor(BaseRayMapBatchActor):
    """模拟 GPU 处理的 Actor"""
    
    def __init__(self, multiplier: float = 2.0, exclude_columns=None):
        super().__init__(exclude_columns)
        self.multiplier = multiplier
    
    def _call(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """模拟 GPU 加速计算"""
        values = batch.get("value", np.array([]))
        # 模拟 GPU 计算
        processed = values * self.multiplier
        return {"gpu_processed": processed}


def example_gpu_actor():
    """示例：GPU Actor（Xenna 执行）"""
    print("\n" + "="*60)
    print("示例 4: GPU Actor（Xenna 执行）")
    print("="*60)
    
    # 创建 Xenna Stage（带 GPU 资源）
    gpu_stage = create_xenna_actor_stage(
        actor_class=GPUProcessingActor,
        actor_kwargs={"multiplier": 3.0},
        batch_size=16,
        num_cpus=2.0,
        num_gpus=1.0,  # 请求 1 个 GPU
    )
    
    # 创建输入任务
    input_tasks = [
        Task(id=i, value=float(i))
        for i in range(1, 11)
    ]
    
    # 创建 Pipeline
    stage_spec = pipelines_v1.StageSpec(
        stage=gpu_stage,
        num_workers=1,  # GPU 通常少量 workers
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
    
    print(f"输入: {len(input_tasks)} 个数值")
    print("使用 GPU 资源: num_gpus=1.0")
    
    # 注意：实际执行需要有 GPU 可用
    # results = pipelines_v1.run_pipeline(pipeline_spec)
    print("\n注意：此示例需要 GPU 资源才能执行")
    print("配置：batch_size=16, num_cpus=2.0, num_gpus=1.0")


# ========== 使用 XennaExecutor 的高层接口 ==========

def example_with_xenna_executor():
    """示例：使用 XennaExecutor 执行 Actor Pipeline"""
    print("\n" + "="*60)
    print("示例 5: 使用 XennaExecutor（高层接口）")
    print("="*60)
    
    # 注意：这需要将 XennaActorStage 包装成 ProcessingStage
    # 或者直接使用低层 API
    
    # 创建 Stages
    tokenizer_stage = create_xenna_actor_stage(
        actor_class=TextTokenizerActor,
        num_cpus=1.0,
    )
    
    # 创建输入任务
    input_tasks = [
        Task(id=1, text="Xenna executor example"),
        Task(id=2, text="Actor adapter with Xenna"),
    ]
    
    # 直接使用低层 API
    stage_spec = pipelines_v1.StageSpec(
        stage=tokenizer_stage,
        num_workers=2,
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
    
    print(f"输入: {len(input_tasks)} 个文档")
    results = pipelines_v1.run_pipeline(pipeline_spec)
    
    print(f"\n输出: {len(results)} 个单词")
    for i, task in enumerate(results):
        print(f"  {i+1}. {task}")
    
    return results


if __name__ == "__main__":
    import ray
    
    # 初始化 Ray
    ray.init(
        ignore_reinit_error=True,
        runtime_env={
            "env_vars": {"RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES": "0"}
        },
    )
    
    try:
        # 运行示例
        print("Xenna Actor Adapter 示例")
        print("=" * 60)
        
        # 示例 1: FlatMap
        example_flatmap_with_xenna()
        
        # 示例 2: MapBatch
        example_mapbatch_with_xenna()
        
        # 示例 3: 多阶段 Pipeline
        example_multi_stage_pipeline()
        
        # 示例 4: GPU Actor（仅显示配置）
        example_gpu_actor()
        
        # 示例 5: XennaExecutor
        example_with_xenna_executor()
        
        print("\n" + "="*60)
        print("所有示例完成！")
        print("="*60)
        
    finally:
        ray.shutdown()

