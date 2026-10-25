# ext/path 同步记录

本次同步 `atomic.py`、`calc.py`、`pathstr.py` 及对应测试，基于 Alasio 最新实现：

- `atomic.py`：保留失败时的临时文件清理、空文件复制、空生成器建空文件，并统一 `atomic_write_stream()` 的实现。
- `calc.py`：`subpath_to()` 在非子路径时返回 `None`，新增严格的 `subpath()`；根路径和 cwd 归一化保持 `/`。
- `pathstr.py`：同步 `subpath()` / `subpath_to()` 和原子流写入接口。
- 测试：迁移 `test_calc.py`、`test_pathstr.py` 以及 `atomic/` 下的完整测试，并改写 `alasio.` 前缀为 `oas.`。

验证：`581 passed`。
