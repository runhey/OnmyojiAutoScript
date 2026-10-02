filelock 基准对比(Windows / Python 3.14,mean 值,来源 `tests/oas/ext/file/test_bench_filelock.py`):

| 维度 | 场景 | msvcrt(原生) | SQLiteFileLock | 差距 |
|---|---|---|---|---|
| T1 无竞争 | 25 次 acquire+release | 1.48 ms | 16.1 ms | ~11× |
| T2 线程竞争 | 2 线程各 50 次 | 0.63 ms | 73.9 ms | ~117× |
| T3 跨进程 | 2 子进程各 1000 轮(含启动) | 67.5 ms | 1468 ms | ~22× |
| T4 超时路径 | 单次被拒 acquire | 69 μs | 30.8 ms | ~450× |

— SQLiteFileLock 在所有维度均显著慢于 Windows 原生 msvcrt.locking。

ext/file 已同步 10 个源码文件:filelock.py、hash.py、jsonfile.py、loaddll.py、loadpy.py、msgspecfile.py、watchdog.py、yamlfile.py、deep.py、yamlconfig.py。

| 文件 | 测试 | 迁移改动 |
|---|---|---|
| jsonfile.py | test_jsonfile / test_jsonfile_indent | 去掉 py<3.9 兼容分支(3.14 不需要) |
| loaddll.py | test_loaddll | 无 |
| loadpy.py | test_loadpy(保留 fs.patch_open_code) | 无 |
| msgspecfile.py | 无(Alasio 侧本就无测试) | 无 |
| watchdog.py | 无(Alasio 侧本就无测试) | `from ..path.calc` 改绝对导入 |
| hash.py | 无 | import 前缀 |
| filelock.py | test_filelock | import 前缀 |
| yamlfile.py | test_yamlfile | import 前缀 |
| deep.py | test_deep_get/iter/pop/set | 无(零依赖,字节级复制) |
| yamlconfig.py | test_yamlconfig/test_yamlconfig_comment | import 前缀;内联 `_split_help`(替代 config_dev 的 format_i18n);`logger` → `print` |

— 全部通过(179 passed / 9 skipped);filelock 竞态用例靠把 loser 预算 0.2s 降到 0.01s 让不等式方向稳健而修复。

yamlconfig.py 已完成:msgspecerror 从 PyPI 安装(0.21.1.1,钉 msgspec==0.21.1);deep.py 已迁入;format_i18n 内联为 `_split_help`(不拖 config_dev);logger 改用 print 输出(不迁 logger 包,减少依赖)。