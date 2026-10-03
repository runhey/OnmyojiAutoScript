# base/exception 迁移

`alasio/base/exception.py` 58 行 → `script/misc/exception.py`，逐字节一致（无 import）。

## 本地重叠
- `module/exception.py` 已有 8 个同名类（ScriptError / GameStuckError / GameBugError / GameTooManyClickError / EmulatorNotRunningError / GameNotRunningError / GamePageUnknownError / RequestHumanTakeover）。两套并存，跨模块 `isinstance` 会失效。
- Alasio 独有 `TaskStop`；OAS 独有 `ScriptEnd` / `TaskEnd` 及 Campaign*/Map* 5 个本地类。

## 去向
消费者 `config/base/config_task.py`、`base/scheduler/scheduler.py`、`base/base.py` 将来都落 `oas/`，届时需搬进 oas。本轮按规则留 `script/misc`。
