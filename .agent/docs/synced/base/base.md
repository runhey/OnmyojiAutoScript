# base 迁移盘点

`alasio/base` 10 项 4604 行 vs `oas/base` 7 文件 + `utils/` 4 文件。
AST 级别扫描 297 个符号，33 个同名命中（31 个签名一致）。

| # | Alasio `alasio/base` | 行 | OAS `oas/base` | 行 | 关系 | 判定 |
|---|---|---|---|---|---|---|
| **1** | `image/color.py` | 505 | `utils/utils.py`（15 个同名函数） | 941 | **重复** 3 个 body 一致 / 12 个 Alasio 更重 | 别搬 |
| **2** | `image/draw.py` | 274 | `utils/utils.py`（`resize` `get_bbox`） | ↑ | **重复** `resize` 一致，`get_bbox` 不同 | 别搬 |
| **3** | `image/imfile.py` | 505 | `utils/utils.py`（`crop` `image_channel` `image_size`） | ↑ | **重复** `image_size` 一致，另 2 个不同 | 别搬 |
| **4** | `image/imgif.py` | 91 | — | — | 独一份（imageio 动图） | OAS 没有 |
| **5** | `image/impillow.py` | 88 | — | — | 独一份（Pillow 兜底） | OAS 没有 |
| **6** | `image/impreview.py` | 47 | — | — | 独一份 | OAS 没有 |
| **7** | `op/slist.py` | 199 | `utils/grids.py` `SelectedGrids` | 377 | **重复** 同类改名，4 方法 body 一致 | 别搬 |
| **8** | `op/area.py` `Area`/`Point` | 915 | `utils/points.py` `Points`/`Lines` | 395 | 部分重叠 点线集合 vs 带仿射变换 | **可搬**（AST 确认 OAS 无 `Area`/`Point`） |
| **9** | `op/color.py` `RGB` | 29 | — | — | 无撞名 | **可搬** |
| **10** | `op/rng.py` | 69 | `ext/path/atomic.py` `random_id()` | — | 1 个撞名**签名不同**（不同函数）；另 3 个无撞名 | **可搬** |
| **11** | `timer.py` `Timer` | 221 | `timer.py` `Timer` | 170 | **同名冲突** 11 方法 2 一致 9 不同 | **要合并** |
| **12** | `filter.py` | 69 | `filter.py` `class Filter` | 131 | 纯撞名 零重叠 | **可搬**（改名避让） |
| **13** | `pretty.py` | 76 | `ext/perf.py` 内联 `pretty_time` | — | 3 个已处理 / 3 个无 | **可搬**（补 3 个） |
| **14** | `exception.py` 9 类 | 58 | — | — | 无撞名 | **可搬** |
| **15** | `servertime.py` | 494 | — | — | 无撞名，卡在 msgspec | 等 `op/` 落地 |
| **16** | `state.py` 9 类 | 679 | `decorator.py` 撞名 `Config`/`.when()` | 201 | **不同东西** 零重叠 | 卡在 `msgspecerror`+`logger`；**生产调用方 0** |
| **17** | `base.py` `ModuleBase` | 123 | — | — | 无撞名 | 卡在 config/device/logger |
| **18** | `scheduler/` 4 文件 | 568 | — | — | 无撞名 | 卡在 backend/config/device |
| — | — | — | `cBezier.py` 160 / `retry.py` 123 / `protect.py` 18 / `log_highlighter.py` 31 | 332 | **OAS 原生**，Alasio 无对应 | 已有 |

## 三类分组

| 判定 | 项 | 行数 |
|---|---|---|
| **别搬（重复）** | #1 #2 #3 #7 | 1483 |
| **要合并（冲突）** | #11 `timer.py` | 221 |
| **可直接搬（零撞名）** | #8 #9 #10 #12 #13 #14 | 1245 |
| **卡上层依赖** | #15 #16 #17 #18 | 1864 |

`image/{imgif,impillow,impreview}`（226 行）既不重复也没被覆盖，但没被任何东西调用
（`image/` 整体 14 处调用全在 `assets/` `device/`），跟着 #1-#3 一起不进 OAS 更一致。

## timer.py 冲突细节（唯一需合并项）

| | Alasio | OAS |
|---|---|---|
| 时钟 | **`time.monotonic()`** | `time.time()` |
| 状态字段 | `_start` / `_access` | `_current` / `_reach_count` |
| `reached()` 未启动 | 显式 `return True`（快速首次尝试） | 靠 `time.time() - 0` 巨大值巧合为真 |
| Alasio 独有 | `from_seconds()` `set()` `add_count()` `current_time()` `current_count()` | |
| OAS 独有 | | `remain()` + 模块级 `future_time` `past_time` `future_time_range` `time_range_active` |

11 个方法里只有 `reached_and_reset` 和 `__str__` body 一致。
**Alasio 用 `monotonic()` 更对** —— 计时器不受 NTP 校正/系统时间跳变影响。

## 顺带：6 处迁移遗留

`oas/base/` 里 6 处 `from module.logger import logger` 没跟着改（`module/` 完整存在所以能跑，
但 `oas/logger` 已迁好）：

```
oas/base/decorator.py:44,148    oas/base/filter.py:4
oas/base/protect.py:4           oas/base/retry.py:6     oas/base/timer.py:157
```
