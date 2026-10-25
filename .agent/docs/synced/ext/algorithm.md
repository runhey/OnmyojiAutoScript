# `oas/ext/algorithm` 与 Alasio 的当前差异

- `oas` 当前没有 `oas.speedup` 模块。`bit2coding_encode_c.py`、`vlenint_encode_c.py`、`pathcomb_encode_c.py` 对该模块使用可选导入；不可用时直接回退到 Python 实现。
- `bit2coding_encode_python.py` 使用标准库 `itertools.batched`，没有依赖 Alasio 的 `backport.batch`。
- `pathcomb_encode_python.py` 使用 `str.removeprefix()`，没有依赖 Alasio 的 `backport.removeprefix`。
