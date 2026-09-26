# Alasio testing → OAS / Migration Notes

> 规则 / Rule：**filesystem 源码 + 测试全部同步**，仅改包名前缀与记录类型 / sources + tests synced; only prefix + record type changed.

## 同步源码 / SYNCED Sources (5)

| 文件 / File | 改动 / Changes |
|-------------|----------------|
| `base.py` | `msgspec.Struct` → `@dataclass(slots=True)`，逻辑不变 / records converted |
| `__init__.py` | `alasio.` → `oas.`；`LogWriter` try/except（缺失自动忽略） / prefix + try/except |
| `fake_fs.py` | docstring 前缀 / comment only |
| `entry.py` | 原样 / unchanged |
| `file_object.py` | 原样 / unchanged |

## 同步测试 / SYNCED Tests (8) → `tests/oas/testing/filesystem/`

| 文件 / File | 改动 / Changes |
|-------------|----------------|
| `conftest.py` / `test_entry.py` / `test_file_object.py` | 仅前缀 / prefix only |
| `test_filesystem_base.py` | msgspec 断言 → `dataclasses.is_dataclass`；`PathStr` → `pathlib.Path` |
| `test_fake_fs.py` | `file_read_bytes` → 原生 open/read；`PathStr` → `pathlib.Path`；`deploy.pack.job_reset` → `oas.backport.cjk` |
| `test_integration.py` | `importorskip('oas.ext.path')` 挂起 / parked |
| `test_thread_safety.py` | `importorskip('oas.ext.concurrent.threadpool')` 挂起 / parked |
| `test_logger_fakefs.py` | `importorskip('oas.logger')` 挂起 / parked |

## 要点 / Notes

- 无 `msgspec` 依赖；测试 **190 passed, 4 skipped**（3 个挂起 + POSIX 平台跳过）/ 190 passed, 4 skipped
- 挂起的 3 个文件：对应模块（`oas.ext.path` / `oas.ext.concurrent` / `oas.logger`）迁移后自动复活，无需改动 / auto-resume when the modules land
- `oas.ext.file.loadpy` 未搬——`patch_open_code()` 相关集成待其迁移
- 已迁 `drop.py` / `managed_process.py` / `patch_time.py` / `timeout.py` 及配套测试（`timeout.py` / `patch_time.py` 原样；差异见下）/ migrated with tests (timeout/patch_time unchanged)
- `drop.py`：`logger.info` → `print`；原因：OAS 无 `oas.logger`（`oas/logger` 仅有空 `__init__.py`，`logger.py` 未迁），以 `print` 输出、测试改用 pytest `capsys` 断言 / reason: no `oas.logger` yet, print + capsys instead
- env：`managed_process.py` 的 `ALASIO_ROOT` → `OAS_ROOT`；原因：新建 `oas/ext/env.py`，用标准库 `os.path.dirname` 上跳 3 层替代 Alasio 的 `PathStr.uppath(3)`（OAS 无 `PathStr`）定位仓库根 / reason: no `PathStr`, new `oas/ext/env.py` resolves root with stdlib
- 测试：`test_patch_time.py` / `test_patch_time_direct_import.py` 退出后验证处的 `datetime.utcnow()` → `datetime.now(tz=utc).replace(tzinfo=None)`；原因：`utcnow()` 自 Python 3.12 弃用，OAS 在 3.14 上运行会亮警告（with 块内的 Mock 调用不动）/ reason: `utcnow()` deprecated since 3.12; mock-path calls untouched