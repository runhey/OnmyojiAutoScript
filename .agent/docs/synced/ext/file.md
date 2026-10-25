# `oas/ext/file` 与 Alasio 的当前差异

同步基线：Alasio `962c6c390`（2026-10-24，`origin/master`）。OAS 原先停在 10-02 的快照，本次补齐
`66306f010`（09-25）之后的上游增量。下表的 `+N/-M` 是 OAS 相对上游新增/删掉的行数（比较前两边都
按 OAS 的 ruff 配置格式化，并把 `alasio` 归一到 `oas`）。复核：

```bash
git diff --numstat 66306f010 962c6c390 -- alasio/ext/file tests/ext/file
```

验证：`tests/oas/ext/file` 342 passed / 9 skipped；全仓 `tests/oas` 6459 passed / 63 skipped。

## 与上游逐字一致

- 源码：`filelock.py`、`loaddll.py`、`loadpy.py`、`msgspecfile.py`、`yamlfile.py`
- 测试：`test_filelock.py`、`test_jsonfile_indent.py`、`test_loaddll.py`、`test_loadpy.py`、`test_yamlfile.py`

## 源码差异

| 文件 | 差异 |
| --- | --- |
| `hash.py`、`watchdog.py` | 上游用相对导入（`from ..path.atomic` / `from ..path.calc`），OAS 一律绝对导入（`from oas.ext.path...`） |
| `jsonfile.py` | `+10/-23`：删掉 `json_loads()` 的 py<3.9 分支（3.14 直接 `json.loads(data)`，不再传 `encoding`） |
| `yamlconfig.py` | `+46/-11`：`format_i18n` 内联成 `_split_help()` / `_split_help_iter()`（不拖 `oas.config_dev`）；`logger.info/warning` 改成 `print`（不拖 `oas.logger`） |
| `tomlfile.py` | `+2/-27`：删掉 `get_tomllib()` 的 `tomli` 回退（py<3.11 兼容层），只留 `toml_loads()`，直接用标准库 `tomllib` |
| `__init__.py` | 两边都是空文件 |

## 测试差异

| 文件 | 差异 |
| --- | --- |
| `test_yamlconfig.py` | `+219/-213`：上游 25 处 `with logger.mock_capture_writer() as capture:` 改成 pytest `capsys`——每个 capture region 前先 `capsys.readouterr()` 清一次，region 后取 `.out`；`capture.fd/backend.any_contains` 与 `levels == ['WARNING','INFO']` 三类断言合并成 stdout 文本断言 |
| `test_tomlfile.py` | `+7/-30`：随 `get_tomllib` 删掉 `TestGetTomllib`（4 例）；补 1 例 `test_uses_stdlib_tomllib` 对原生 `tomllib` |
| `test_jsonfile.py` | `-7`：删掉 py<3.9 `encoding` 弃用告警的 `pytestmark` |
| `test_yamlconfig_comment.py` | `±1`：注释里的 `format_i18n` → `_split_help` |
| `test_bench_filelock.py` | OAS 独有（上游没有这个基准）。随新锁语义改两处：T2 的注释；T4 改用显式 `owner='other-owner'`——锁现在按线程 id 持有，同线程重入直接 `RuntimeError`，不再是 `FilelockTimeout` |
| `tests/ext/file/__init__.py` | 上游 `a3667bedd`（09-25）给所有测试模块补了空 `__init__.py`（避免 pytest 同名模块冲突），`tests/oas/ext/file/` 没有 |

另外，两边所有 `alasio` / `ALASIO` 字样在 OAS 侧统一成 `oas` / `OAS`：导入前缀、`env.OAS_TEMP`、
示例数据与文档串。

## 本次同步进来的上游提交

| 提交 | 内容 | 落地 |
| --- | --- | --- |
| `f9796eadb`（10-02） | `LINE_WIDTH = 120` + `yaml_dumps(width=...)` | `yamlfile.py` + `test_yamlfile.py` |
| `bcf69d391`（10-03） | `data` 改 `cached_property`（懒读）、`write(template=False, skip_same=True)` + 抽出 `_write()` | `yamlconfig.py` + `test_yamlconfig.py` |
| `487e2c0bf`（10-16） | loaddll 测试声明 ctypes restype | `test_loaddll.py` |
| `9d2a0244e`（10-19） | 新增 `tomlfile.py` | 新文件 + `test_tomlfile.py` |
| `dedf07835`、`ca20f702b`（10-21） | filelock 测试目录隔离、临时目录改用临时根 | `test_filelock.py` |
| `640eadedf`（10-21） | loadpy 的 str 子类路径用例 | `test_loadpy.py` |
| `ce11d8eab`（10-22） | 锁改成"每文件一份状态 + 非重入 + `acquire(owner=)`" | `filelock.py` + `test_filelock.py` |
| `ae9331602`（10-23） | `loaddll` 接受版本化 so（`libc.so.6`、`libSystem.B.dylib`） | `loaddll.py` + `test_loaddll.py` |
| `82e785497`（10-23） | loadpy 测试改用 `cache_from_source()`（`sys.pycache_prefix`） | `test_loadpy.py` |

## filelock 基准（本次运行，2026-10-25，Windows / Python 3.14，mean）

| 维度 | 场景 | msvcrt(原生) | SQLiteFileLock | 差距 |
| --- | --- | --- | --- | --- |
| T1 无竞争 | 25 次 acquire+release | 1.08 ms | 15.2 ms | ~14× |
| T2 线程竞争 | 2 线程各 50 次 | 0.52 ms | 49.6 ms | ~96× |
| T3 跨进程 | 2 子进程各 1000 轮(含启动) | 52.0 ms | 1211 ms | ~23× |
| T4 超时路径 | 单次被拒 acquire | 62 μs | 3.66 ms | ~59× |

— 来源 `tests/oas/ext/file/test_bench_filelock.py`（`--benchmark-only`，单次运行，SQLite 侧方差较大）。
SQLiteFileLock 在所有维度仍显著慢于 Windows 原生 msvcrt.locking。

> 本文替换了 10-02 的迁移记录与旧基准表：旧表的数字是 `ce11d8eab` 之前那版实现（每实例重入、无
> `owner` 参数）跑出来的。