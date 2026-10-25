# config：动态组的展平时机

Alasio 在**生成期**把多实例组展平成独立字段/类，模型里没有 list；
OAS 把 list 留在模型里，只在**序列化 / 存储边界**展平。
即 Alasio「生成时展平、运行时按需聚合」，OAS「运行时就是 list、落盘时展平」。

## Alasio

| 阶段 | 做法 | 锚点 |
|---|---|---|
| 定义 | YAML 是 source，group 是字段集合，多实例只在这里标记 | `config/*.yaml`（目录待核实） |
| 生成 | codegen 把每个实例展开成独立 Struct 类，产物里没有 list 字段 | `alasio/config_dev/gen/gen_alasio.py` → `alasio/config/alasio/alasio_model.py`（auto-generated） |
| 导出 | 再生成一个模块，集中暴露展开出来的类 | `alasio/config/alasio/group_export.py`（auto-generated） |
| 运行时 | 要按 list 用时临时聚合，回写时再展开回扁平 | `config.base.dynamic.to_list/to_dict`（待核实） |

实例体现在**类名**上：`Scheduler` 展开出 `SchedulerU00` / `SchedulerU04` / `SchedulerUedit`，
组合变体各成一个类（`SchedulerStaticU04(SchedulerStatic, SchedulerU04)`）。
字段直接写在类上，模型本身始终扁平。

## OAS

- `list[Group]` 由 `oas/config/models/registry.py::is_dynamic_annotation` 识别，
  `ConfigModelRegistry.dynamic_fields()` 列出动态字段。
- 运行时模型就是 list；`oas/config/runtime/config_access.py` 提供按索引排序的只读视图。
- 落盘时展平：`oas/config/models/tasks.py::to_dict()` 把每个实例写成 `field@index`，
  `from_dict()` 反解回 list；存储层每条实例一行（`oas/config/entry/store.py`、
  `entry/mod_config.py` 的 `_read_dynamic_field` / `_write_dynamic_field`）。

## 记一笔

之前把「OAS 的 serializer 展平」当成了 Alasio 的机制，方向正好相反：
Alasio 的展平在生成期，list 只是临时视图；OAS 的 list 是固有形态，展平只发生在边界。

## 待核实

`config.base.dynamic.to_list/to_dict` 在 `D:\Project\Alasio\alasio` 里找不到（全仓无
`dynamic.py`，`alasio/config/` 下也没有 dynamic 模块）。可能是 Alas 上游的接口，
或是我们准备自己建的 —— 先别当成 Alasio 的既有代码写进结论。