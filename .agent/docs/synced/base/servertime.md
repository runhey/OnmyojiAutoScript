# base/servertime 迁移

`alasio/base/servertime.py` 494 行 → `script/misc/servertime.py`，逐字节一致。

差异只有 import：

- 源：`from alasio.base.op import random_normal_distribution_int` → `from script.misc.op import ...`
- 测试：`tests/base/test_servertime.py` → `tests/script/misc/test_servertime.py`，`alasio.base[.servertime]` → `script.misc.*`、`alasio.testing.patch_time` → `oas.testing.patch_time`

## 本地重叠（未动，以 Alasio 为准）

- `random_time` / `parse_second` ↔ `oas/base/utils/utils.py::ensure_time`：同为区间正态随机，语义重叠。
- OAS 原生 `module/config/utils.py::get_server_next_update` / `parse_tomorrow_server` 暂未接入。

测试 `tests/script/misc/test_servertime.py` 125 passed。
