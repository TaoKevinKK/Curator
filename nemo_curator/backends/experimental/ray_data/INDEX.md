# Actor Adapter Layer 文档索引

欢迎查看 Actor Adapter Layer 的完整文档。这个索引将帮助您找到所需的信息。

## 📚 快速导航

### 新手入门

1. **[快速开始指南](./QUICK_START.md)** ⭐ 推荐首选
   - 5 分钟快速上手
   - 常见使用模式
   - 完整的端到端示例
   - 调试和性能优化技巧

2. **[示例代码](./actor_adapter_example.py)**
   - 5 个可运行的完整示例
   - 涵盖所有适配器类型
   - GPU 使用示例

### 深入理解

3. **[设计文档](./ACTOR_ADAPTER_README.md)**
   - 完整的设计说明
   - 每种适配器的详细介绍
   - 使用场景分析
   - 参数配置指南
   - 最佳实践

4. **[架构对比](./ARCHITECTURE_COMPARISON.md)**
   - adapter.py vs actor_adapter.py 详细对比
   - 使用场景决策指南
   - 资源管理对比
   - 性能考虑

5. **[架构图](./ARCHITECTURE_DIAGRAM.md)**
   - 可视化架构设计
   - 数据流转图
   - 决策流程图
   - Mermaid 图表

6. **[设计总结](./ACTOR_ADAPTER_SUMMARY.md)**
   - 整体设计概述
   - 关键特性总结
   - 文件清单
   - 未来改进方向

### 代码和测试

7. **[核心实现](./actor_adapter.py)**
   - 完整的适配器实现
   - 4 种专门的适配器类型
   - 工厂函数
   - 完整的类型注解

8. **[单元测试](../../../tests/test_actor_adapter.py)**
   - 13 个测试用例
   - 覆盖所有功能
   - 可作为使用示例参考

## 📖 按主题查找

### 我想了解...

#### 基础概念

- **什么是 Actor Adapter?** 
  → 查看 [设计总结](./ACTOR_ADAPTER_SUMMARY.md#设计概述)
  
- **为什么需要这个设计?**
  → 查看 [设计文档](./ACTOR_ADAPTER_README.md#设计目标)
  
- **与 adapter.py 有什么区别?**
  → 查看 [架构对比](./ARCHITECTURE_COMPARISON.md#详细对比表)

#### 如何使用

- **我想快速开始**
  → 查看 [快速开始指南](./QUICK_START.md)
  
- **我需要处理单行数据**
  → 查看 [FlatMap 示例](./QUICK_START.md#模式-1-行级转换一对一)
  
- **我需要批量处理数据**
  → 查看 [MapBatch 示例](./QUICK_START.md#模式-3-批处理转换)
  
- **我需要在 GPU 上运行**
  → 查看 [GPU 示例](./QUICK_START.md#模式-4-有状态的-actor如模型推理)

#### 配置和优化

- **如何配置资源?**
  → 查看 [资源配置指南](./QUICK_START.md#资源配置指南)
  
- **如何优化性能?**
  → 查看 [性能优化](./QUICK_START.md#性能优化技巧)
  
- **Actor 和 Task 模式有什么区别?**
  → 查看 [模式选择](./ARCHITECTURE_COMPARISON.md#actortask-模式选择)

#### 高级主题

- **如何处理错误?**
  → 查看 [错误处理流程](./ARCHITECTURE_DIAGRAM.md#错误处理流程)
  
- **exclude_columns 如何工作?**
  → 查看 [排除列](./QUICK_START.md#排除列exclude-columns)
  
- **如何与 Pipeline 集成?**
  → 查看 [组合使用](./ARCHITECTURE_COMPARISON.md#组合使用示例)

## 🎯 按角色查找

### 我是...

#### 初学者
推荐阅读顺序：
1. [快速开始指南](./QUICK_START.md) - 理解基本用法
2. [示例代码](./actor_adapter_example.py) - 运行示例
3. [设计总结](./ACTOR_ADAPTER_SUMMARY.md) - 了解整体设计

#### 开发者
推荐阅读顺序：
1. [设计文档](./ACTOR_ADAPTER_README.md) - 深入理解设计
2. [核心实现](./actor_adapter.py) - 查看实现细节
3. [单元测试](../../../tests/test_actor_adapter.py) - 理解测试覆盖

#### 架构师
推荐阅读顺序：
1. [架构对比](./ARCHITECTURE_COMPARISON.md) - 对比分析
2. [架构图](./ARCHITECTURE_DIAGRAM.md) - 可视化理解
3. [设计总结](./ACTOR_ADAPTER_SUMMARY.md) - 整体把握

## 📊 文档统计

| 文档类型 | 文件名 | 主要内容 | 页数估计 |
|---------|--------|---------|---------|
| 入门指南 | QUICK_START.md | 快速上手、常见模式 | 8-10 页 |
| 设计文档 | ACTOR_ADAPTER_README.md | 完整设计说明 | 12-15 页 |
| 架构对比 | ARCHITECTURE_COMPARISON.md | 对比分析、选择指南 | 15-18 页 |
| 架构图 | ARCHITECTURE_DIAGRAM.md | 可视化架构 | 8-10 页 |
| 设计总结 | ACTOR_ADAPTER_SUMMARY.md | 整体概述 | 6-8 页 |
| 示例代码 | actor_adapter_example.py | 可运行示例 | ~250 行 |
| 核心实现 | actor_adapter.py | 适配器实现 | ~470 行 |
| 单元测试 | test_actor_adapter.py | 测试用例 | ~350 行 |

**总计**: ~60 页文档 + ~1070 行代码

## 🔍 快速查找

### 常见问题

<details>
<summary><b>Q: 我应该使用 adapter.py 还是 actor_adapter.py?</b></summary>

**A**: 
- 如果构建完整的 Pipeline → 使用 `adapter.py`
- 如果实现单个操作 → 使用 `actor_adapter.py`

详见: [选择指南](./ARCHITECTURE_COMPARISON.md#选择指南)
</details>

<details>
<summary><b>Q: 如何在 GPU 上运行我的 Actor?</b></summary>

**A**: 
```python
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_gpus=1,  # 每个 actor 1 个 GPU
    concurrency=4,  # 使用 Actor 模式
)
```

详见: [GPU 配置](./QUICK_START.md#gpu-密集型任务)
</details>

<details>
<summary><b>Q: Actor 和 Task 模式如何选择?</b></summary>

**A**: 
- 设置了 `concurrency` 或 `num_gpus` → Actor 模式
- 否则 → Task 模式

详见: [模式选择](./ARCHITECTURE_COMPARISON.md#actortask-模式选择)
</details>

<details>
<summary><b>Q: 如何优化批处理大小?</b></summary>

**A**: 
- CPU 操作: 100-1000
- GPU 操作: 16-128
- 内存受限: 1-32

详见: [性能优化](./QUICK_START.md#性能优化技巧)
</details>

<details>
<summary><b>Q: 如何调试我的 Actor?</b></summary>

**A**: 
1. 先用 Task 模式测试
2. 使用小数据集
3. 添加日志输出
4. 查看 Ray Dashboard

详见: [调试技巧](./QUICK_START.md#调试技巧)
</details>

## 🚀 开始使用

### 方式 1: 从示例开始（推荐）

```bash
# 运行示例代码
cd /path/to/Curator
python -m nemo_curator.backends.experimental.ray_data.actor_adapter_example
```

### 方式 2: 从快速开始开始

阅读 [快速开始指南](./QUICK_START.md)，然后编写你的第一个 Actor。

### 方式 3: 从测试开始

```bash
# 运行单元测试
cd /path/to/Curator
pytest tests/test_actor_adapter.py -v
```

## 📝 代码片段索引

### 基础使用

```python
# 最简单的 FlatMap Actor
class MyActor(BaseRayFlatMapActor):
    def _call(self, row):
        return [{"result": process(row)}]

adapter = create_adapter_for_actor(
    actor_class=MyActor,
    num_cpus=1,
)
result = adapter.process_dataset(dataset)
```

→ 详见: [快速开始](./QUICK_START.md#步骤-2-定义你的-actor)

### GPU 使用

```python
# GPU 模型推理
class GPUActor(BaseRayMapBatchActor):
    def __init__(self, model_path, exclude_columns=None):
        super().__init__(exclude_columns)
        self.model = None
        self.model_path = model_path
    
    def _call(self, batch):
        if self.model is None:
            self.model = load_model_to_gpu(self.model_path)
        return {"pred": self.model.predict(batch["input"])}

adapter = create_adapter_for_actor(
    actor_class=GPUActor,
    actor_kwargs={"model_path": "/path/to/model"},
    batch_size=32,
    num_gpus=1,
    concurrency=4,
)
```

→ 详见: [GPU 示例](./QUICK_START.md#模式-4-有状态的-actor如模型推理)

### 资源配置

```python
# 完整的资源配置
adapter = create_adapter_for_actor(
    actor_class=MyActor,
    actor_kwargs={"param": "value"},
    batch_size=64,
    num_cpus=2.0,
    num_gpus=0.5,
    concurrency=(2, 8),  # 动态范围
)
```

→ 详见: [资源配置](./QUICK_START.md#资源配置指南)

## 🔗 相关资源

### 内部资源

- [base_actors.py](./base_actors.py) - Actor 基类定义
- [adapter.py](./adapter.py) - Stage 适配器
- [utils.py](./utils.py) - 工具函数

### 外部资源

- [Ray Data 官方文档](https://docs.ray.io/en/latest/data/data.html)
- [Ray Core 文档](https://docs.ray.io/en/latest/ray-core/walkthrough.html)
- [PyArrow 文档](https://arrow.apache.org/docs/python/)

## 📞 获取帮助

如果您在使用过程中遇到问题：

1. **查看文档** - 使用本索引快速定位相关内容
2. **运行示例** - 参考 [actor_adapter_example.py](./actor_adapter_example.py)
3. **查看测试** - 测试用例展示了各种使用场景
4. **检查日志** - 使用 Ray Dashboard 查看详细日志

## 🎯 下一步

根据您的需求选择：

- 🚀 **快速开始** → [QUICK_START.md](./QUICK_START.md)
- 📚 **深入学习** → [ACTOR_ADAPTER_README.md](./ACTOR_ADAPTER_README.md)
- 🏗️ **理解架构** → [ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md)
- 💻 **查看代码** → [actor_adapter.py](./actor_adapter.py)

---

**文档版本**: 1.0  
**最后更新**: 2025-10-13  
**维护者**: NeMo Curator Team

Happy coding! 🎉

