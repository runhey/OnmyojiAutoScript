# base/state 迁移

`alasio/base/state.py` 679 行 → `script/misc/state.py`，逻辑一致，只改 import（`alasio.logger` → `oas.logger`）。

## 内容
- `_StateMeta` 元类：注解字段 → `msgspec.defstruct` 校验模型 + `__dict_defaults__`；禁止实例化，字段须有类型+静态默认。
- 生命周期：`GlobalState`（跨任务保留）/ `TaskState`（任务切换重置）/ `GameStateBase`（预置 `server`/`lang`）。
- 字段操作：`update` / `batch_set` / `update_from_class` / `is_modified` / `get_default` / `reset_field` / `reset_all_fields` / `reset_all_subclasses` / `match` / `match_server` / `match_lang`。
- 分发：`when()`（`_StateDispatcher`，链式=或，`@when()`=兜底，都不中调最后定义并 warn）。
- 测试：`patch()` / `patch_server` / `patch_lang`（`_StatePatchContext`，退出恢复、异步兼容）。
- `Config.when()`（`_ConfigDispatcher`）：按实例 `self.config` 分发。

## 与 OAS 现状重叠
- `Config.when()` ↔ `oas/base/decorator.py::Config.when`：用法几乎一样（按 config 选项分方法实现），但 OAS 版 method-only、注册不去重、无 `@when()` 兜底/最后函数语义。**两套 `Config` 并存，未合并。**
- `cached_property`：测试改用 `oas.ext.cache.cached_property`。
- `TaskState.reset_all_subclasses()` 在 Alasio 由 scheduler 在任务切换/空闲调用；OAS 调度循环未迁，**新树暂无调用方**。

## 依赖
`msgspec`、`msgspecerror`（OAS 已装）、`msgspec._core.Factory`（私有 API，msgspec 0.21.1）。

## 验证
`tests/script/misc/state/` 193 passed。
