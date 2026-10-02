ext/algorithm 已同步 14 源码 + 19 测试(2257 passed / 2 skipped),零第三方依赖。

| 文件 | 测试 | 迁移改动 |
|---|---|---|
| const / zigzag / diffcooding / lcp / lz77 / checksum | 各自 test_* | 无,字节一致 |
| unpack / vint / vlenint / pathlen_coding / pathlcs / pathlcs_v3 | 各自 test_* | import 前缀 |
| bit2coding | test_bit2coding_* (6) | import 前缀;`backport.batch.batched` → `itertools.batched` |
| pathcomb | test_pathcomb | import 前缀;`backport.removeprefix` → `str.removeprefix`,调用点改写 |

— 10 个文件仅改 import 行,零逻辑差异;补空 `__init__.py`(Alasio 侧为命名空间包)。

未迁 `pathlcs_compare.py`:非 pytest 收集目标,依赖 `alasio.git`(OAS 无 `oas/git`)。