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
PySpark DataFrame 和 Ray Dataset 互相转换示例

演示三种转换方法：
1. 通过 Parquet 文件（推荐用于大数据集）
2. 通过内存/Pandas（适合小数据集）
3. 通过 Arrow（零拷贝转换）

运行要求:
    pip install pyspark ray pyarrow pandas
"""

import tempfile
import os
import ray
from pyspark.sql import SparkSession


def setup():
    """初始化 Ray 和 Spark"""
    print("初始化 Ray 和 Spark...")
    ray.init(ignore_reinit_error=True)
    
    spark = SparkSession.builder \
        .appName("PySparkRayConversion") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .master("local[*]") \
        .getOrCreate()
    
    # 设置日志级别
    spark.sparkContext.setLogLevel("WARN")
    
    return spark


def example_1_parquet_method():
    """方法 1: 通过 Parquet 文件转换（推荐）"""
    print("\n" + "="*60)
    print("方法 1: 通过 Parquet 文件转换")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    
    # === PySpark → Ray Dataset ===
    print("\n[1] PySpark DataFrame → Ray Dataset")
    
    # 创建 PySpark DataFrame
    df_spark = spark.createDataFrame([
        (1, "apple", 1.5),
        (2, "banana", 2.0),
        (3, "cherry", 3.5),
        (4, "date", 4.0),
        (5, "elderberry", 5.5),
    ], ["id", "fruit", "price"])
    
    print("原始 PySpark DataFrame:")
    df_spark.show()
    
    # 通过 Parquet 转换
    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = os.path.join(tmpdir, "data.parquet")
        
        # 保存为 Parquet
        df_spark.write.mode("overwrite").parquet(parquet_path)
        print(f"已保存到: {parquet_path}")
        
        # 用 Ray 读取
        ds_ray = ray.data.read_parquet(parquet_path)
        print(f"\nRay Dataset (行数: {ds_ray.count()}):")
        print(ds_ray.take(5))
    
    # === Ray Dataset → PySpark ===
    print("\n[2] Ray Dataset → PySpark DataFrame")
    
    # 创建 Ray Dataset
    ds_ray = ray.data.from_items([
        {"id": 10, "fruit": "fig", "price": 6.0},
        {"id": 11, "fruit": "grape", "price": 7.5},
        {"id": 12, "fruit": "honeydew", "price": 8.0},
    ])
    
    print("原始 Ray Dataset:")
    print(ds_ray.take_all())
    
    # 通过 Parquet 转换
    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = os.path.join(tmpdir, "data.parquet")
        
        # 保存为 Parquet
        ds_ray.write_parquet(parquet_path)
        print(f"\n已保存到: {parquet_path}")
        
        # 用 Spark 读取
        df_spark = spark.read.parquet(parquet_path)
        print("\nPySpark DataFrame:")
        df_spark.show()


def example_2_memory_method():
    """方法 2: 通过内存转换（适合小数据集）"""
    print("\n" + "="*60)
    print("方法 2: 通过内存转换")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    
    # === PySpark → Ray Dataset ===
    print("\n[1] PySpark DataFrame → Ray Dataset (via Pandas)")
    
    # 创建 PySpark DataFrame
    df_spark = spark.createDataFrame([
        (1, "red", 100),
        (2, "blue", 200),
        (3, "green", 300),
    ], ["id", "color", "value"])
    
    print("原始 PySpark DataFrame:")
    df_spark.show()
    
    # 转换为 Pandas（会收集到内存）
    df_pandas = df_spark.toPandas()
    print(f"\nPandas DataFrame (shape: {df_pandas.shape}):")
    print(df_pandas)
    
    # 从 Pandas 创建 Ray Dataset
    ds_ray = ray.data.from_pandas(df_pandas)
    print(f"\nRay Dataset (行数: {ds_ray.count()}):")
    print(ds_ray.take_all())
    
    # === Ray Dataset → PySpark ===
    print("\n[2] Ray Dataset → PySpark DataFrame (via Pandas)")
    
    # 创建 Ray Dataset
    ds_ray = ray.data.from_items([
        {"id": 10, "color": "yellow", "value": 400},
        {"id": 11, "color": "purple", "value": 500},
    ])
    
    print("原始 Ray Dataset:")
    print(ds_ray.take_all())
    
    # 转换为 Pandas
    df_pandas = ds_ray.to_pandas()
    print(f"\nPandas DataFrame (shape: {df_pandas.shape}):")
    print(df_pandas)
    
    # 从 Pandas 创建 Spark DataFrame
    df_spark = spark.createDataFrame(df_pandas)
    print("\nPySpark DataFrame:")
    df_spark.show()


def example_3_arrow_method():
    """方法 3: 通过 Arrow 转换（高性能）"""
    print("\n" + "="*60)
    print("方法 3: 通过 Arrow 转换")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    
    # === PySpark → Ray Dataset ===
    print("\n[1] PySpark DataFrame → Ray Dataset (via Arrow)")
    
    # 创建 PySpark DataFrame
    df_spark = spark.createDataFrame([
        (1, "cat", 10.5),
        (2, "dog", 20.3),
        (3, "bird", 30.7),
    ], ["id", "animal", "weight"])
    
    print("原始 PySpark DataFrame:")
    df_spark.show()
    
    # 转换为 Arrow Table (通过 Pandas)
    df_pandas = df_spark.toPandas()
    arrow_table = df_pandas.to_arrow()
    print(f"\nArrow Table (行数: {arrow_table.num_rows}):")
    print(arrow_table)
    
    # 从 Arrow 创建 Ray Dataset
    ds_ray = ray.data.from_arrow(arrow_table)
    print(f"\nRay Dataset (行数: {ds_ray.count()}):")
    print(ds_ray.take_all())
    
    # === Ray Dataset → PySpark ===
    print("\n[2] Ray Dataset → PySpark DataFrame (via Arrow)")
    
    # 创建 Ray Dataset
    ds_ray = ray.data.from_items([
        {"id": 10, "animal": "fish", "weight": 5.2},
        {"id": 11, "animal": "hamster", "weight": 2.1},
    ])
    
    print("原始 Ray Dataset:")
    print(ds_ray.take_all())
    
    # 转换为 Arrow Table
    arrow_table = ds_ray.to_arrow()
    print(f"\nArrow Table (行数: {arrow_table.num_rows}):")
    print(arrow_table)
    
    # 从 Arrow 创建 Pandas，然后 Spark
    df_pandas = arrow_table.to_pandas()
    df_spark = spark.createDataFrame(df_pandas)
    print("\nPySpark DataFrame:")
    df_spark.show()


def example_4_complete_workflow():
    """完整工作流示例"""
    print("\n" + "="*60)
    print("完整工作流: PySpark → Ray 处理 → PySpark")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    
    # 1. 从 PySpark 开始
    print("\n[步骤 1] 创建 PySpark DataFrame")
    df_spark = spark.createDataFrame([
        (1, "apple", 1.5),
        (2, "banana", 2.0),
        (3, "cherry", 3.5),
        (4, "date", 4.0),
    ], ["id", "fruit", "price"])
    
    print("原始数据:")
    df_spark.show()
    
    # 2. 转换为 Ray Dataset
    print("\n[步骤 2] 转换为 Ray Dataset")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "data.parquet")
        df_spark.write.mode("overwrite").parquet(path)
        ds_ray = ray.data.read_parquet(path)
    
    print(f"Ray Dataset (行数: {ds_ray.count()})")
    
    # 3. 用 Ray 处理数据
    print("\n[步骤 3] 用 Ray 处理数据 (价格打折 20%)")
    
    def apply_discount(row):
        row["price"] = row["price"] * 0.8
        row["discounted"] = True
        return row
    
    ds_processed = ds_ray.map(apply_discount)
    print("处理后的数据:")
    print(ds_processed.take_all())
    
    # 4. 转换回 PySpark
    print("\n[步骤 4] 转换回 PySpark DataFrame")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "processed.parquet")
        ds_processed.write_parquet(path)
        df_result = spark.read.parquet(path)
    
    print("最终结果:")
    df_result.show()
    
    # 5. 继续用 Spark 处理
    print("\n[步骤 5] 继续用 Spark 处理")
    df_summary = df_result.groupBy("discounted").agg(
        {"price": "avg", "id": "count"}
    )
    print("汇总统计:")
    df_summary.show()


def example_5_large_dataset():
    """大数据集处理示例"""
    print("\n" + "="*60)
    print("大数据集处理示例")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    
    # 创建一个较大的数据集
    print("\n[1] 创建大数据集")
    df_spark = spark.range(0, 10000).toDF("id")
    df_spark = df_spark.withColumn("value", df_spark["id"] * 2)
    df_spark = df_spark.withColumn("category", df_spark["id"] % 10)
    
    print(f"数据集大小: {df_spark.count()} 行")
    df_spark.show(5)
    
    # 转换为 Ray Dataset
    print("\n[2] 转换为 Ray Dataset")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "large_data.parquet")
        
        # 保存时进行分区
        df_spark.write.mode("overwrite") \
            .option("compression", "snappy") \
            .parquet(path)
        
        # Ray 读取（指定并行度）
        ds_ray = ray.data.read_parquet(path, parallelism=4)
    
    print(f"Ray Dataset 行数: {ds_ray.count()}")
    print(f"Ray Dataset 块数: {ds_ray.num_blocks()}")
    
    # 并行处理
    print("\n[3] 并行处理")
    
    def process_batch(batch):
        import pandas as pd
        df = pd.DataFrame(batch)
        df["processed_value"] = df["value"] * 1.5
        return df.to_dict("list")
    
    ds_processed = ds_ray.map_batches(process_batch, batch_size=1000)
    
    print("处理完成，查看样本:")
    print(ds_processed.take(5))
    
    # 统计
    print("\n[4] 计算统计信息")
    stats = ds_processed.aggregate(
        ray.data.AggregateFn(
            init=lambda k: [0, 0],  # [sum, count]
            accumulate_row=lambda a, row: [a[0] + row["processed_value"], a[1] + 1],
            merge=lambda a1, a2: [a1[0] + a2[0], a1[1] + a2[1]],
            finalize=lambda a: a[0] / a[1] if a[1] > 0 else 0,
            name="avg_processed_value",
        )
    )
    print(f"平均处理后的值: {stats}")


def cleanup():
    """清理资源"""
    print("\n" + "="*60)
    print("清理资源...")
    print("="*60)
    
    spark = SparkSession.builder.getOrCreate()
    spark.stop()
    ray.shutdown()
    
    print("完成！")


def main():
    """主函数"""
    print("="*60)
    print("PySpark DataFrame 和 Ray Dataset 转换示例")
    print("="*60)
    
    try:
        # 初始化
        spark = setup()
        
        # 运行示例
        example_1_parquet_method()
        example_2_memory_method()
        example_3_arrow_method()
        example_4_complete_workflow()
        example_5_large_dataset()
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        cleanup()


if __name__ == "__main__":
    main()



