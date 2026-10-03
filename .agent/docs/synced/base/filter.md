# base/filter 迁移

`alasio/base/filter.py` 69 行 → `script/misc/filter.py`，逐字节一致，只用 stdlib（`re` / `collections.deque`）。

- 与 `oas/base/filter.py::Filter` 类同名不同物，不同模块不冲突。
- 消费者 `config/entry/mod_scheduler.py::parse_filter` 将来落 `oas/config/entry/`，届时需搬进 oas。本轮按规则留 `script/misc`。

测试 `tests/script/misc/test_filter_parse.py`（Alasio 原样，仅改 import 为 `script.misc.filter`）。
