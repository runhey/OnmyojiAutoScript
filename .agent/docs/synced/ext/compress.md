ext/compress 已同步 2 源码 + 2 测试(137 passed),字节级零差异。

| 文件 | 测试 | 迁移改动 |
|---|---|---|
| algo_lzma.py | test_algo_lzma | 无,字节一致 |
| algo_zstd.py | test_algo_zstd | 无,字节一致 |

— 源码只依赖 stdlib `lzma` 与 `zstandard`,无 `alasio` import;测试仅改import 前缀。新增依赖 `zstandard>=0.23.0`(实测 0.25.0),已登记进 pyproject。

下游为 `deploy/pack/decode_base.py` 与 `deploy_dev/pack/{pack_diff,pack_repo}.py`,均未迁,故暂无生产调用方。