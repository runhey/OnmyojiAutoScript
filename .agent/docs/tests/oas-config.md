# oas/config 测试计划

> 状态快照：2026-10-23
>
> 当前基线：`tests/oas/config` + `tests/oas/mod` 共 **1021 passed**。
>
> 本文只记录测试设计与覆盖状态，不包含测试实现。代码变更后请同步更新本文件。

## 1. 范围

覆盖 `oas/config/` 与配置所依赖的 `oas/mod/` 脚手架：

```text
oas/config/
├── models/      Pydantic 模型、组件、registry、菜单默认值
├── groups/      可复用 Group（SchedulerGroup）
├── entry/       dict ↔ MsgPack ↔ SQLite、Mod 接口实现、菜单实现
├── table/       config / key / scan / menu 表
├── runtime/     ConfigMod API、ConfigAccess 缓存与访问层
└── show/        本地演示脚本与示例模型
```

测试原则：

1. **Pydantic 是唯一模型权威**：序列化测试走 `to_dict()` / `from_dict()` / `Codec`。
2. **存储测试使用 `:memory:`**：每个测试结束后清理 named singleton。
3. **registry 是进程级全局状态**：测试类名唯一，不断言 registry 总数。
4. **不重复已有 434 个组件模型测试**；新测试聚焦组合、边界和集成。
5. 失败路径与成功路径同等重要：非法值、缺失行、损坏 payload、事务回滚都必须断言。

## 2. 运行方式

```powershell
# 全部 config + mod 测试
.\.venv\Scripts\python.exe -m pytest tests/oas/config tests/oas/mod -q

# 只跑 runtime
.\.venv\Scripts\python.exe -m pytest tests/oas/config/runtime -q

# 只跑本轮新增的序列化/访问层测试
.\.venv\Scripts\python.exe -m pytest tests/oas/config/entry tests/oas/config/runtime/test_config_access.py -q

# 性能用例（可选）
.\.venv\Scripts\python.exe -m pytest tests/oas/config --benchmark-only
```

## 3. 当前覆盖情况

| 层 | 测试文件 | 用例数 | 状态 |
| --- | --- | ---: | --- |
| `models/args.py` 组件 | `test_option/options/input/...`（12 个组件文件） | 434 | ✅ 覆盖充分 |
| `models/groups.py` | `models/test_groups.py` | 18 | ✅ |
| `models/tasks.py` | `models/test_tasks.py` | 136 | ✅ schema + IO + 异常 |
| `models/registry.py` | `models/test_registry.py` | 20 | ✅ |
| `models/base.py` | `models/test_base.py` | 13 | ✅ |
| `models/menu.py` | `models/test_models_menu.py` | 4 | ✅ |
| `show/debug_models.py` | `show/test_debug_models.py` | 4 | ✅ |
| `groups/scheduler.py` | `groups/test_scheduler.py` | 19 | ✅ |
| `entry/*.py` | `entry/test_codec/error/model/mod_config/mod_menu/mod_store.py` | 119 | ✅ |
| `runtime/*.py` | `runtime/test_config_access/config_mod/config_state/menu_mod.py` | 158 | ✅ |
| `table/*.py` | `table/test_config/key/menu/scan.py` | 70 | ✅ |
| `oas/mod/*.py` | `tests/oas/mod/test_adapter/const/info/utils.py` | 26 | ✅ |
| **合计** | | **1021** | **全部通过** |

## 4. 测试文件布局（一个源文件一个测试文件）

| 源文件 | 测试文件 |
| --- | --- |
| `models/args.py` | `models/test_option.py` / `test_options.py` / `test_option_item.py` / `test_input.py` / `test_input_area.py` / `test_slider.py` / `test_switch.py` / `test_button.py` / `test_time.py` / `test_time_delta.py` / `test_date_time.py` / `test_cron.py`（组件级拆分，沿用既有约定） |
| `models/base.py` | `models/test_base.py` |
| `models/groups.py` | `models/test_groups.py` |
| `models/tasks.py` | `models/test_tasks.py` |
| `models/registry.py` | `models/test_registry.py` |
| `models/menu.py` | `models/test_models_menu.py` |
| `show/debug_models.py` | `show/test_debug_models.py` |
| `groups/scheduler.py` | `groups/test_scheduler.py` |
| `entry/codec.py` | `entry/test_codec.py` |
| `entry/error.py` | `entry/test_error.py` |
| `entry/model.py` | `entry/test_model.py` |
| `entry/mod_config.py` | `entry/test_mod_config.py` |
| `entry/mod_menu.py` | `entry/test_mod_menu.py` |
| `entry/mod_store.py` | `entry/test_mod_store.py` |
| `runtime/config_access.py` | `runtime/test_config_access.py` |
| `runtime/config_mod.py` | `runtime/test_config_mod.py` |
| `runtime/config_state.py` | `runtime/test_config_state.py` |
| `runtime/menu_mod.py` | `runtime/test_menu_mod.py` |
| `table/config.py` | `table/test_config.py` |
| `table/key.py` | `table/test_key.py` |
| `table/menu.py` | `table/test_menu.py` |
| `table/scan.py` | `table/test_scan.py` |
| `oas/mod/adapter.py` | `tests/oas/mod/test_adapter.py` |
| `oas/mod/const.py` | `tests/oas/mod/test_const.py` |
| `oas/mod/info.py` | `tests/oas/mod/test_info.py` |
| `oas/mod/utils.py` | `tests/oas/mod/test_utils.py` |
| 共享 fixture | `tests/oas/config/conftest.py` |

## 5. P0：闭环正确性

| ID | 模块 | 测试对象 | 关键用例 | 现状 |
| --- | --- | --- | --- | --- |
| P0-1 | `models/groups.py` | `GroupBase.to_dict/from_dict` | 全组件 round-trip；组件序列化；默认值；未知字段；非法值；子类返回 | ✅ |
| P0-2 | `models/tasks.py` | `TaskBase.to_dict/from_dict` | 只含单 Group；排除标量与动态列表；字段顺序；默认值；未知 group；非法 payload；必填 Group | ✅ |
| P0-3 | `entry/codec.py` | `Codec.encode/decode` | 类型 round-trip；空 dict；Unicode；TypeError/ValueError；bytearray/memoryview；`Struct` 兼容 | ✅ |
| P0-4 | `entry/mod_store.py` | `TaskStore.save/load` | 行字段；round-trip；更新不增行；replace 删过期；实例隔离；默认值；过期 taskclass；空名；回滚；损坏行 | ✅ |
| P0-5 | `runtime/config_access.py` | 缓存 | 幂等；模板跳过；`config_changed`；`refresh`；`release` | ✅ |
| P0-6 | `runtime/config_access.py` | Group 读取 | `_load_group` 缓存/默认值/损坏；`_task_class` / `_group_class`；`init_task`；`__getattr__` | ✅ |
| P0-7 | `runtime/config_access.py` | GroupProxy | 读写；私有属性拒绝；批量方法包装；`repr/str` | ✅ |
| P0-8 | `runtime/config_access.py` | 持久化 | `register_modify`；auto-save；`save` 失败恢复；批量上下文嵌套/异常 | ✅ |
| P0-9 | `runtime/config_access.py` | override | `override`；常量；非法值；`temporary`；`override_clear` | ✅ |
| P0-10 | `runtime/config_access.py` | 其它访问 | `bound`；`bound_get`；`cross_get`；`cross_set`；无 Task 实例 | ✅ |
| P0-11 | `entry/mod_menu.py` | `MenuEntry` | 顺序；空 group；重复；级联删除；事务回滚；`seed_defaults`；名称/参数校验；移动/复制异常 | ✅ |
| P0-12 | `entry/mod_menu.py` | `modmenu` / `MenuMod` | 19 个方法签名/CRUD/错误/跨 scheme copy/move；entry 挂载与 config_name 校验 | ✅ |
| P0-13 | `table/menu.py` | 三张 menu 表 | DDL；唯一约束；排序；级联；`upsert_scheme` | ✅ |

## 6. P1：装饰器与边界

| ID | 模块 | 测试对象 | 关键用例 | 现状 |
| --- | --- | --- | --- | --- |
| P1-1 | `entry/mod_config.py` | `_decorate` 契约 | 22 个方法签名/注解去 `result`；`__wrapped__` 保留；实现先于方法体 | ✅ |
| P1-2 | `entry/mod_config.py` | `_shared_adapter` | 惰性创建/复用；config_name 变化；非 adapter；缺 entry_info/config_name | ✅ |
| P1-3 | `entry/mod_config.py` | `config_*` 边界 | 空 batch；重复 event；跨 group 回滚；post_edit 失败；read 过滤 | ✅ 主路径 + 边界 |
| P1-4 | `entry/mod_config.py` | `cfg_*` 边界 | task/group/arg 生命周期；无效名字；跨 task copy；未知对象 | ✅ 主路径 + 边界 |
| P1-5 | `entry/mod_config.py` | snapshot / data_version | 行读取；版本 tuple；空表 | ✅ |
| P1-6 | `entry/error.py` | `ConfigError` | 默认值；`from_pydantic`；loc 回退；MsgPack round-trip；omit_defaults | ✅ |
| P1-7 | `entry/model.py` | Struct | `ConfigResult` 独立 events；refs 解码；`TaskItem`；`DecoderCache`；JSON 缓存回退 | ✅ |
| P1-8 | `models/registry.py` | registry | 两个 Group；泛型注解；`filter_menu`；KeyError；只读映射；qualified_name | 🟡 同名重复注册等未覆盖 |
| P1-9 | `models/menu.py` | `DEFAULT_MENU` | 分类顺序；去重；DebugTask 出现；非空字符串 | ✅ |
| P1-10 | `models/base.py` | `ConfigBase` / helpers | 注册/抽象跳过；extra 忽略；schema extra 优先级；temporal/boolean 默认规则 | ✅ |
| P1-11 | `runtime/config_state.py` | 状态初始化 | 默认字段；template → auto_save=False；非 template 前缀 | ✅ |
| P1-12 | 集成 | `ConfigAccess` + `ConfigMod` | 改值自动落库；重读；缓存；模板不落库 | 🟡 部分由 ConfigAccess 覆盖 |

## 7. P2：外围与兼容

| ID | 模块 | 测试对象 | 关键用例 | 现状 |
| --- | --- | --- | --- | --- |
| P2-1 | `show/debug_models.py` | demo 不变量 | 每个 TaskClass 恰好 2 个不同 GroupClass；`to_dict`；store round-trip | ✅ |
| P2-2 | `groups/scheduler.py` | `SchedulerGroup` | 默认值；序列化；round-trip；schema | ✅ |
| P2-3 | `table/config.py` | ConfigTable 补充 | `read_task_rows` 组合；`get_data_version`；cursor 复用；空条件；删除 | ✅ |
| P2-4 | `oas/mod/*` | adapter/info/const/utils | adapter 接口；entry 默认/copy/iter；const；名字校验 | ✅ |
| P2-5 | 兼容 | 旧数据 | Struct 行（Codec 已测）；未知/缺失参数；过期 taskclass；损坏行 | 🟡 部分 |
| P2-6 | 并发 | ConfigAccess | 线程本地 batch_depth；并发 register_modify；RLock save | ❌ |
| P2-7 | 性能 | 可选 | `Codec`；`TaskStore`；`config_cache` 命中 | ❌ |
| P2-8 | 版本/迁移 | 未实现 | 等 `KeyTable` schema version 方案落地 | ❌ |

## 8. 当前失败

**无。** 2026-10-23 复跑 `tests/oas/config tests/oas/mod`：1021 passed。

已有 menu 测试（`table/test_menu.py`、`runtime/test_menu_mod.py`）本轮未改动，当前全绿。

## 9. 测试基础设施

1. **registry 隔离**：测试类名唯一；不要断言 registry 总数；必要时在隔离用例里 `config_model_registry.clear()`。
2. **`:memory:` 清理**：使用 `tests/oas/config/conftest.py` 的 `memory_config` fixture；清理 `ConfigTable`、`KeyTable` 与 `SQLITE_POOL`。
3. **新增测试优先复用 `memory_config`**，不要再各自复制一份清理逻辑。
4. **`modmenu` 的入口**：`MenuMod` 每个实例挂载一个 `MenuEntry`（`__menu_entry__`）；测试用 `MenuMod(":memory:")` 即可，不需要再手写 dummy 类。
5. **已删除的旧测试**：`tests/oas/config/entry/test_task_config.py` 已随旧 API 删除，不要恢复。
6. **断言风格**：优先断言返回值/DB 行/异常类型与消息；涉及缓存时同时断言 `_dict_row` / `_dict_group` / `_modified` 的内部状态。

## 10. 维护约定

- 修改 `oas/config/` 的公开 API 时，同步更新本文件的“现状”列。
- 新增测试文件后，更新第 3、4 节。
- 修复失败用例后，更新第 8 节。
- 版本/迁移方案落地后，把 P2-8 拆成具体测试项。

## 11. 本轮执行记录（2026-10-23）

按“一个源文件一个测试文件”收敛，所有 `*_more` / `*_errors` / `*_edges` / `*_extra` 补充文件已合并删除：

| 目录 | 测试文件数 | 用例数 |
| --- | ---: | ---: |
| `tests/oas/config/models` | 17 | 625 |
| `tests/oas/config/groups` | 1 | 19 |
| `tests/oas/config/entry` | 6 | 119 |
| `tests/oas/config/runtime` | 4 | 158 |
| `tests/oas/config/table` | 4 | 70 |
| `tests/oas/config/show` | 1 | 4 |
| `tests/oas/mod` | 4 | 26 |
| **合计** | **37** | **1021** |

说明：

- `models/args.py` 仍按组件拆成 12 个测试文件，这是既有约定；其余源文件均一一对应。
- `models/menu.py` 使用 `test_models_menu.py`，避免与 `table/test_menu.py` 的 pytest 模块名冲突。
- `entry/mod_config.py` 与 `runtime/config_mod.py` 分别对应装饰器契约和公开 API 两个测试文件。

验证结果：**1021 passed**；`ruff check tests/oas/config tests/oas/mod` 全部通过。
