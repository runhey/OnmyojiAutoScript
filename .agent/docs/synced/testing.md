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
- 未搬 `drop.py` / `managed_process.py` / `patch_time.py` / `timeout.py`（测试亦未搬）