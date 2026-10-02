# ext/concurrent — 不迁

| 模块 | 行 | 调用方 | 干什么 |
|---|---|---|---|
| `threadpool.py` | 627 | 9 | trio 风格线程池 |
| `cmd.py` | 183 | 2 | subprocess 封装 |
| `prioritycapacity.py` | 116 | 0 | 优先级令牌桶 |
| `prioritycapacity_trio.py` | 106 | 0 | 同上，需 trio |
| `prioritythreadpool.py` | 230 | 0 | 优先队列线程池 |
| `processpool.py` | 328 | 0 | 多进程池 |
| `processworker.py` | 33 | 0 | 子进程入口 |

## `threadpool.py` 调用方

| 文件 | 干什么 |
|---|---|
| `git/file/gitobject.py` | 读 git loose + pack object |
| `git/stage/gitcommit.py` | 预读 loose object 再 commit |
| `git/stage/gitreset.py` | 校验待 reset 文件 |
| `codegen/asar/pack.py` | 写文件进 asar |
| `assets_dev/parse.py` | 解码图片算 bbox/mean |
| `config/table/scan.py` | 读表行 / mod 名 |
| `config_dev/gen/gen_task_entry.py` | 扫任务入口 |
| `deploy_dev/simple_pip.py` | 写文件 / 生成 pyc |
| `device/search/windows.py` | 枚举模拟器 / adb |

## `cmd.py` 调用方

| 文件 | 干什么 |
|---|---|
| `codegen/ruff/ruff_format.py` | 跑 ruff format |
| `deploy_dev/simple_pip.py` | 查已装包 |

结论：调用方在 OAS 侧全未迁，无实际需求。将来迁 `oas/git` 时只需搬 `threadpool.py` + `cmd.py`。