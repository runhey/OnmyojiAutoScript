# OAS 数据域与运行时架构

## 总体结构

```text
oas/
├── config/
│   ├── models/
│   ├── groups/
│   ├── entry/
│   ├── table/
│   └── runtime/
├── state/
│   ├── models/
│   ├── groups/
│   ├── entry/
│   ├── table/
│   └── runtime/
├── statistics/
│   ├── models/
│   ├── groups/
│   ├── entry/
│   ├── table/
│   └── runtime/
├── scheduler/
│   ├── models/
│   ├── runtime/
│   └── engine/
└── db/
```

## 依赖方向

```text
                         scheduler/
                 ┌───────────────┐
                 │ models        │
                 │ runtime       │
                 │ engine        │
                 └───────┬───────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
 config/runtime    state/runtime    statistics/runtime
       │                 │                 │
       ▼                 ▼                 ▼
 config/entry      state/entry      statistics/entry
       │                 │                 │
       ▼                 ▼                 ▼
 config/table      state/table      statistics/table
       └─────────────────┼─────────────────┘
                         ▼
                        db/
```

依赖只能从上层指向下层：

```text
scheduler
    ↓
数据域 runtime
    ↓
数据域 entry
    ↓
数据域 table
    ↓
db
```

`db` 不反向依赖 `config`、`state`、`statistics` 或 `scheduler`。

## 各层职责

### `config`

保存任务配置。配置模型使用 Pydantic 定义，Group 可以被多个 Task 复用。

- `models`：配置基础模型和参数模型。
- `groups`：可复用的配置 Group 定义。
- `entry`：配置领域业务接口，负责读取、校验、修改和保存配置。
- `table`：配置数据库表定义。
- `runtime`：配置运行时缓存和当前 Task/Group 的访问状态。

配置数据库的基本粒度是一个 `taskclass + task + groupclass + group` 对应一条记录，Group 内容保存为二进制值。

### `state`

保存任务执行过程中需要恢复的状态。状态单独使用数据表，因为不是每个配置 Group 都有状态，且状态会独立演进。

- `models`：状态模型。
- `groups`：可复用的状态 Group 定义。
- `entry`：状态读取、更新和恢复接口。
- `table`：状态数据库表定义。
- `runtime`：状态缓存。

### `statistics`

保存任务运行记录、统计数据和审计结果。它是可选的记录系统，不应成为任务正常执行的必要依赖。

- `models`：执行记录、统计结果、审计结果模型。
- `groups`：可复用的统计记录结构。
- `entry`：统计写入、查询和审计处理接口。
- `table`：统计数据库表定义。
- `runtime`：统计缓存和批量写入状态。

### `scheduler`

调度器是独立的运行时引擎，不属于某一个数据域。

- `models`：调度器内部模型。
- `runtime`：调度器内存状态。
- `engine`：调度循环、任务选择和任务执行流程。

调度器启动时从 `config` 读取初始配置；运行过程中维护自己的调度状态，并按需要同步到 `config`、`state` 或 `statistics`。

### `db`

`db` 是通用 SQLite 基础设施：

- 连接池和连接生命周期管理。
- Cursor 和事务。
- 数据库文件重命名、删除和连接回收。
- 通用表抽象和 CRUD。

`db` 不负责：

- Pydantic 模型业务校验。
- MsgPack 编解码。
- Task、Group、Arg 的业务含义。
- 调度逻辑。

`ConfigTable` 只处理数据库行和原始二进制值；`KeyTable` 的通用元数据接口额外提供 MsgPack 编解码，业务数据校验仍由对应数据域的 `entry` 层负责。

## 数据库隔离

三个主要数据域分别拥有自己的 SQLite 数据库文件：

```text
config 数据库：任务配置
state 数据库：任务恢复状态
statistics 数据库：执行记录、统计和审计
```

这样可以让配置、状态和统计独立迁移、备份和演进。调度器只通过各数据域的运行时接口访问它们，不直接操作 SQLite。
