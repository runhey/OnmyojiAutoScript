# Alasio backport → OAS 迁移记录 / backport Migration Notes
> 原则 / Rule：**用到的才搬**，3.14 已经内置的能力直接删，不重复造轮子。

## 二、没搬（9）及简短说明 / NOT Migrated (9)

| # | 原文件 / Original | 在 3.14 下 | 简短说明 / Why not |
|---|-------------------|-----------|--------------------|
| 1 | `__init__.py` 内的 `removeprefix` / `removesuffix` / `to_literal` / `process_cpu_count` | 全内置 | 3.9+ 内置前三个，3.13 内置 `process_cpu_count`，无需回填 / all built-in |
| 2 | `batch.py` | 内置 `itertools.batched` | 3.12+ 直接可用，删 / built-in since 3.12 |
| 3 | `strenum.py` | 内置 `StrEnum` | 3.11+ 直接可用，删 / built-in since 3.11 |
| 4 | `rich/rich_14_1.py` | extract 补丁 | 只需 py<3.11 + rich<14.3 的 exceptiongroup 显示，3.14 用不到 / only for py<3.11 |
| 5 | `rich/rich_14_3.py` | 同上 | 同上 / same as above |
| 6 | `patch.py` 内的 `patch_mimetype` | — | OAS 暂无 mimetypes 需求，要时说一声可捡回 / no mimetypes need now |
| 7 | `patch.py` 内的 `patch_threadpool_executor_maxworker` | 内置行为 | 3.13+ 标准行为已默认，删 / built-in default in 3.13+ |
| 8 | `patch.py` 内的 `fix_py37_subprocess_communicate` | — | 3.7 Windows 专属 bug，删 / py3.7-only Windows bug |
| 9 | `literal.py` | — | 配置生成用（to_literal 系），与 logger 无关 / config-gen only |

## 三、搬运约定 / Conventions

> **规则 / Rule：** 3.14 已原生实现而**未搬源码**的功能（`str.removeprefix/removesuffix`、`Literal[*items]`、`os.process_cpu_count`、`itertools.batched`/`StrEnum`）——测试仍要保留，改为**直接测原生实现** / Functions **not migrated** because Python 3.14 has them built-in — their **tests are still kept**, rewritten to test the **native implementation** directly（见 `tests/oas/backport/`）

