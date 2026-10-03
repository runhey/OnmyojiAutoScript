# base/timer 迁移

`alasio/base/timer.py` 221 行 → `script/misc/timer.py` 286 行：Alasio 核心 + 保留 OAS 独有。

## 换 Alasio 的实现

| 项 | OAS 原 | 现在 |
|---|---|---|
| 时钟 | `time.time` | `time.monotonic` |
| 字段 | `_current` / `_reach_count` | `_start` / `_access` |
| 负值 | 不钳 | `limit`/`count` 钳到 0 |
| 未启动 `reached()` | 靠 `_current=0` 自然 True | 显式 `return True` |
| 装饰器 | `time.time` | `perf_counter` + f-string |
| 新增 | — | `getnow` `from_seconds` `set` `add_count` `current_time` `current_count` `T_TIMER_LIMIT` |

## 保留 OAS 独有

- 函数：`future_time` `past_time` `future_time_range` `time_range_active`
- 方法：`current()`、`remain()`

## 返回差异

- `current()`：改单调时钟且钳 ≥0，类型仍 float
- `remain()`：`_start + limit - monotonic`，字段映射后语义不变；**未启动仍为大负数**
- `reached()`：未启动结果一致

## import

- `show()` → `from oas.logger import logger`
- `from typing import Self, Tuple, Union`（py3.14 原生）

## 验证

冒烟通过；`show()` 实跑输出 `INFO | Timer(limit=.../3, count=0/2)`；`oas/base/timer.py` 未动。
测试 `tests/script/misc/timer/` 37 passed（只改 import，用 `oas.testing.patch_time`）。
