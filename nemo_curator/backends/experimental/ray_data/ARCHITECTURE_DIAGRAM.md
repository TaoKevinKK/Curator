# Actor Adapter Layer 架构图

## 总体架构图

```mermaid
graph TB
    subgraph "用户层 User Layer"
        A1[ProcessingStage 子类]
        A2[BaseRayActor 子类]
    end
    
    subgraph "适配层 Adapter Layer"
        B1[adapter.py<br/>RayDataStageAdapter]
        B2[actor_adapter.py<br/>FlatMapActorAdapter]
        B3[actor_adapter.py<br/>MapBatchActorAdapter]
        B4[actor_adapter.py<br/>MapBatchPyarrowActorAdapter]
        B5[actor_adapter.py<br/>DatasetActorAdapter]
    end
    
    subgraph "Ray Data API Layer"
        C1[map_batches]
        C2[flat_map]
        C3[filter / repartition]
    end
    
    subgraph "Ray Core 分布式执行引擎"
        D1[Task Pool]
        D2[Actor Pool]
        D3[Resource Scheduler]
    end
    
    A1 --> B1
    A2 --> B2
    A2 --> B3
    A2 --> B4
    A2 --> B5
    
    B1 --> C1
    B2 --> C2
    B3 --> C1
    B4 --> C1
    B5 --> C1
    B5 --> C2
    B5 --> C3
    
    C1 --> D1
    C1 --> D2
    C2 --> D1
    C2 --> D2
    C3 --> D1
    
    D3 --> D1
    D3 --> D2
```

## Actor Adapter 详细流程图

```mermaid
flowchart TD
    Start([用户定义 Actor 类]) --> Define[继承 BaseRayActor]
    Define --> Choose{选择 Actor 类型}
    
    Choose -->|一对多行转换| FlatMap[BaseRayFlatMapActor]
    Choose -->|批量数值计算| MapBatch[BaseRayMapBatchActor]
    Choose -->|列式数据操作| PyArrow[BaseRayMapBatchPyarrowActor]
    Choose -->|数据集级操作| Dataset[BaseRayDatasetActor]
    
    FlatMap --> Factory[create_adapter_for_actor]
    MapBatch --> Factory
    PyArrow --> Factory
    Dataset --> Factory
    
    Factory --> Config[配置资源和参数]
    Config --> Resources{检查资源配置}
    
    Resources -->|有 GPU 或 concurrency| ActorMode[Actor 模式]
    Resources -->|否| TaskMode[Task 模式]
    
    ActorMode --> CreateActor[创建 Actor 类包装器]
    TaskMode --> CreateTask[创建 Task 函数包装器]
    
    CreateActor --> MapAPI{选择 Ray Data API}
    CreateTask --> MapAPI
    
    MapAPI -->|FlatMap| API1[dataset.flat_map]
    MapAPI -->|MapBatch| API2[dataset.map_batches]
    MapAPI -->|Dataset| API3[直接调用 actor]
    
    API1 --> Execute[分布式执行]
    API2 --> Execute
    API3 --> Execute
    
    Execute --> Result([返回处理后的 Dataset])
```

## Actor vs Task 模式决策树

```mermaid
flowchart TD
    Start([创建 Adapter]) --> CheckConcurrency{concurrency<br/>是否设置?}
    
    CheckConcurrency -->|是| ActorMode[使用 Actor 模式]
    CheckConcurrency -->|否| CheckGPU{num_gpus<br/>是否 > 0?}
    
    CheckGPU -->|是| ActorMode
    CheckGPU -->|否| TaskMode[使用 Task 模式]
    
    ActorMode --> ActorFeatures[特性:<br/>- 有状态<br/>- 预加载资源<br/>- Actor 池复用<br/>- 适合 GPU 任务]
    
    TaskMode --> TaskFeatures[特性:<br/>- 无状态<br/>- 快速启动<br/>- 无复用开销<br/>- 适合简单转换]
    
    ActorFeatures --> CreateActorClass[创建 Actor 类]
    TaskFeatures --> CreateTaskFunc[创建 Task 函数]
    
    CreateActorClass --> Pool[ActorPoolStrategy]
    CreateTaskFunc --> Direct[直接调用]
    
    Pool --> RayData[Ray Data 执行]
    Direct --> RayData
```

## 数据流转图

```mermaid
flowchart LR
    subgraph "输入"
        I1[Raw Dataset]
    end
    
    subgraph "FlatMap 流程"
        F1[Row: dict] --> F2[_call] --> F3[List of dicts] --> F4[展平]
    end
    
    subgraph "MapBatch Numpy 流程"
        M1[Batch: dict of arrays] --> M2[_call] --> M3[dict of arrays] --> M4[合并]
    end
    
    subgraph "MapBatch PyArrow 流程"
        P1[PyArrow Table] --> P2[_call] --> P3[PyArrow Table] --> P4[输出]
    end
    
    subgraph "Dataset 流程"
        D1[Complete Dataset] --> D2[_call] --> D3[Transformed Dataset] --> D4[输出]
    end
    
    subgraph "输出"
        O1[Processed Dataset]
    end
    
    I1 --> F1
    I1 --> M1
    I1 --> P1
    I1 --> D1
    
    F4 --> O1
    M4 --> O1
    P4 --> O1
    D4 --> O1
```

## Exclude Columns 处理流程

```mermaid
flowchart TD
    Start([输入数据]) --> Check{exclude_columns<br/>设置?}
    
    Check -->|None or []| NoExclude[保留所有列]
    Check -->|list of columns| ExcludeList[排除指定列]
    Check -->|'*'| ExcludeAll[排除所有原始列]
    
    NoExclude --> Process[处理数据]
    ExcludeList --> RemoveColumns[删除指定列]
    ExcludeAll --> RemoveAll[删除所有原始列]
    
    RemoveColumns --> Process
    RemoveAll --> Process
    
    Process --> UserLogic[用户 _call 方法]
    UserLogic --> Result[生成新数据]
    Result --> Merge{合并策略}
    
    Merge -->|FlatMap| MergeRow[合并到行字典]
    Merge -->|MapBatch| MergeBatch[合并到批字典]
    Merge -->|PyArrow| MergeTable[添加到 Table]
    
    MergeRow --> Output([输出结果])
    MergeBatch --> Output
    MergeTable --> Output
```

## 资源分配流程

```mermaid
flowchart TD
    Start([创建 Adapter]) --> GetResources[获取资源配置]
    GetResources --> BuildKwargs[构建 compute_kwargs]
    
    BuildKwargs --> AddCPU{num_cpus<br/>设置?}
    AddCPU -->|是| SetCPU[添加 num_cpus]
    AddCPU -->|否| AddGPU{num_gpus<br/>设置?}
    SetCPU --> AddGPU
    
    AddGPU -->|是| SetGPU[添加 num_gpus]
    AddGPU -->|否| AddConcurrency{concurrency<br/>设置?}
    SetGPU --> AddConcurrency
    
    AddConcurrency -->|是| SetConcurrency[添加 concurrency]
    AddConcurrency -->|否| DefaultKwargs[使用默认配置]
    SetConcurrency --> PassToRay[传递给 Ray Data]
    DefaultKwargs --> PassToRay
    
    PassToRay --> RayScheduler[Ray 资源调度器]
    RayScheduler --> Allocate[分配资源]
    
    Allocate --> CheckAvail{资源可用?}
    CheckAvail -->|是| CreateWorker[创建 Actor/Task]
    CheckAvail -->|否| Wait[等待资源]
    Wait --> CheckAvail
    
    CreateWorker --> Execute([开始执行])
```

## 对比：adapter.py vs actor_adapter.py

```mermaid
graph TB
    subgraph "adapter.py 路径"
        A1[ProcessingStage] --> A2[RayDataStageAdapter]
        A2 --> A3{is_actor_stage?}
        A3 -->|是| A4[create_actor_from_stage]
        A3 -->|否| A5[create_task_from_stage]
        A4 --> A6[RayDataStageActorAdapter]
        A5 --> A7[stage_map_fn]
        A6 --> A8[map_batches]
        A7 --> A8
    end
    
    subgraph "actor_adapter.py 路径"
        B1[BaseRayActor] --> B2[create_adapter_for_actor]
        B2 --> B3{Actor 类型?}
        B3 -->|FlatMap| B4[FlatMapActorAdapter]
        B3 -->|MapBatch| B5[MapBatchActorAdapter]
        B3 -->|PyArrow| B6[PyarrowActorAdapter]
        B3 -->|Dataset| B7[DatasetActorAdapter]
        B4 --> B8[flat_map]
        B5 --> B9[map_batches]
        B6 --> B9
        B7 --> B10[直接调用]
    end
    
    subgraph "Ray Data 执行层"
        A8 --> C1[分布式执行]
        B8 --> C1
        B9 --> C1
        B10 --> C1
    end
```

## 执行生命周期

```mermaid
sequenceDiagram
    participant User as 用户代码
    participant Adapter as Actor Adapter
    participant RayData as Ray Data
    participant Worker as Ray Worker
    
    User->>Adapter: create_adapter_for_actor(MyActor, ...)
    Adapter->>Adapter: 选择适配器类型
    Adapter->>Adapter: 配置资源
    
    User->>Adapter: process_dataset(dataset)
    Adapter->>Adapter: 决定 Actor/Task 模式
    
    alt Actor 模式
        Adapter->>RayData: map_batches/flat_map(ActorClass, ...)
        RayData->>Worker: 创建 Actor 实例
        Worker->>Worker: __init__()
        loop 处理每个批次
            RayData->>Worker: __call__(batch)
            Worker->>Worker: _call(batch)
            Worker-->>RayData: 返回结果
        end
    else Task 模式
        Adapter->>RayData: map_batches/flat_map(task_fn, ...)
        loop 处理每个批次
            RayData->>Worker: task_fn(batch)
            Worker->>Worker: 创建 Actor 实例
            Worker->>Worker: _call(batch)
            Worker-->>RayData: 返回结果
        end
    end
    
    RayData-->>Adapter: 处理后的 Dataset
    Adapter-->>User: 返回结果
```

## 错误处理流程

```mermaid
flowchart TD
    Start([开始处理]) --> Execute[执行 _call]
    
    Execute --> Check{是否出错?}
    Check -->|否| Success[返回结果]
    Check -->|是| Catch[捕获异常]
    
    Catch --> Log[_log_error 记录]
    Log --> ActorType{Actor 类型?}
    
    ActorType -->|FlatMap| ReturnEmpty1[返回空列表 []]
    ActorType -->|MapBatch| ReturnEmpty2[返回空字典 {}]
    ActorType -->|PyArrow| ReturnEmpty3[返回空 Table]
    ActorType -->|Dataset| ReturnEmpty4[返回空 Dataset]
    
    ReturnEmpty1 --> Continue[继续处理其他数据]
    ReturnEmpty2 --> Continue
    ReturnEmpty3 --> Continue
    ReturnEmpty4 --> Continue
    
    Success --> Continue
    Continue --> More{还有数据?}
    
    More -->|是| Execute
    More -->|否| End([处理完成])
```

## 性能优化路径

```mermaid
mindmap
  root((Actor Adapter<br/>性能优化))
    批大小优化
      CPU 密集: 大批(100-1000)
      GPU 密集: 中批(16-128)
      内存受限: 小批(1-32)
    并发度优化
      根据资源动态调整
      使用并发范围 (min, max)
      GPU 任务限制并发
    数据格式优化
      数值计算用 Numpy
      列操作用 PyArrow
      灵活转换用 Dict
    模式选择优化
      轻量任务用 Task
      重初始化用 Actor
      GPU 任务用 Actor
    资源分配优化
      合理设置 num_cpus
      精确分配 num_gpus
      避免资源碎片
```

## 使用场景决策树

```mermaid
flowchart TD
    Start([需要处理数据]) --> Question1{是否需要<br/>Pipeline 编排?}
    
    Question1 -->|是| UseStage[使用 adapter.py<br/>ProcessingStage]
    Question1 -->|否| Question2{操作类型?}
    
    Question2 -->|一对多转换| UseFlatMap[使用 FlatMapActorAdapter]
    Question2 -->|批量数值计算| UseMapBatch[使用 MapBatchActorAdapter]
    Question2 -->|列式数据操作| UsePyArrow[使用 PyArrowActorAdapter]
    Question2 -->|数据集级操作| UseDataset[使用 DatasetActorAdapter]
    
    UseFlatMap --> Config1[配置:<br/>- concurrency<br/>- num_cpus]
    UseMapBatch --> Config2[配置:<br/>- batch_size<br/>- num_cpus<br/>- num_gpus]
    UsePyArrow --> Config3[配置:<br/>- batch_size<br/>- num_cpus]
    UseDataset --> Config4[配置:<br/>- num_cpus<br/>- num_gpus]
    UseStage --> Config5[配置:<br/>- Resources<br/>- batch_size]
    
    Config1 --> Execute([执行处理])
    Config2 --> Execute
    Config3 --> Execute
    Config4 --> Execute
    Config5 --> Execute
```

## 总结

这些架构图展示了 Actor Adapter Layer 的：

1. **总体架构** - 与 adapter.py 的关系和分层设计
2. **详细流程** - 从用户定义到执行的完整流程
3. **决策逻辑** - Actor vs Task 的自动选择
4. **数据流转** - 不同适配器类型的数据处理方式
5. **资源管理** - 资源配置和分配流程
6. **错误处理** - 异常处理和恢复机制
7. **性能优化** - 各种优化策略和路径
8. **使用决策** - 如何选择合适的适配器

这些图表可以帮助开发者更好地理解整个系统的设计和工作原理。

