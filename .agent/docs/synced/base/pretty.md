# base/pretty 迁移

`alasio/base/pretty.py` 76 行 → `oas/base/pretty.py`（`oas/ext/perf.py` 是 oas 消费者，不能放 script/misc）。

- `oas/ext/perf.py` 删掉内联 `pretty_time`，改为 `from oas.base.pretty import pretty_time`。
- `pretty_size` 在 Alasio 全仓无调用（死代码），照搬保留。
- `pretty_value` / `dict2kv` 暂无 OAS 调用方。

测试 `tests/oas/base/test_pretty.py`（`TestPrettyTime` 从 `tests/oas/ext/test_perf.py` 挪来）。
