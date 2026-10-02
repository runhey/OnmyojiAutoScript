# ext/singleton、ext/timez

| 模块 | 源码 | 测试 | 结果 |
|---|---|---|---|
| `singleton.py` | 320 行，**字节级直搬**（仅 LF 规范化） | `test_singleton.py` 614 行 | 39 passed |
| `timez.py` | 127→137 行，重写 | `timez/test_iso.py` 110 行 + `test_timezone.py` 152 行 | 92 passed / 8 skipped |

两个模块生产调用方都是 0（Alasio 侧也是），属于"库面存货"。

## singleton.py

零 `alasio` import（只有 docstring 里的示例类名 `AlasioConfigDB`），所以**整份文件一字未改**，与 Alasio 逐字节相同 —— 以后拿 `diff` 对账能直接出 0 行。docstring 里的 Alasio 示例类名故意保留，不影响运行。

4 个元类共用同一套锁布局，源码注释里已写明原因：

```python
# Per-class singleton storage. Plain (unmangled) names on purpose:
# the SingletonNamed family shares the storage layout across the
# metaclass subclasses, name mangling would split it per class.
cls._singleton_instance = None
cls._singleton_lock = threading.Lock()
```

即 `__init__` 里用 `_singleton_instance` 而非 `__singleton_instance`。因为 `SingletonNamed` 会 `super().__init__` 走到这里，若用双下划线，Python 的名字改写会按**定义它的类**（`Singleton`）加前缀，四个元类就共用同一份存储 —— 这正是期望行为；但若某个子类想独立存储就会分裂。保持单下划线是显式选择，不是遗漏。

## timez.py 的两处改动

### 1. 删掉 3.11+ 冗余的大写 `Z` 兼容

`datetime.fromisoformat` 从 **3.11 起原生支持 `Z`**（实测 3.14.6：`fromisoformat('2023-10-27T15:30:00Z')` → `tzinfo=timezone.utc`）。原实现在 `fromisoformat` 和两个 `to_local_*` 里各内联了一份 `Z`/`z` → `+00:00`，共 3 份冗余。

**但小写 `z` 仍不支持**（实测：`fromisoformat('...z')` → `ValueError`），而 `test_iso.py` 有 `zulu_lowercase_z` 用例，所以只保留小写分支：

```python
if isinstance(text, str) and text.endswith('z'):
    text = text[:-1] + '+00:00'
```

顺带把 3 份重复收进私有 `_parse()`，`to_local_naive` / `to_local_aware` / 公开的 `fromisoformat` 共用。

### 2. 让 `to_local_naive` 走 `get_local_tz()`，测试套件不再依赖本机时区

原实现两条路径都够不着 monkeypatch：

| 函数 | 原实现 | 测试 monkeypatch 的目标 |
|---|---|---|
| `to_local_naive` | `dt_obj.astimezone(None)` —— 读**真实**系统时区 | `time_converter.get_local_tz` |
| `to_local_aware` | 内联 `datetime.now().astimezone().tzinfo` | `time_converter.get_local_tz` |

`get_local_tz()` 的 docstring 写着 *"Isolates the call to datetime.now() so it can be easily patched during tests"* —— 但两个 `to_local_*` 都没调用它，monkeypatch 是空操作。**测试只在本机 UTC+8 时通过**：实测 `TZ=EST5EDT` 下 42 failed / 50 passed。

改成走 `get_local_tz()` 后（语义等价，`astimezone(None)` 就是 `astimezone(get_local_tz())`，但可被替换）：

| 时区 | 改前 | 改后 |
|---|---|---|
| 本机 UTC+8 | 92 passed | 92 passed |
| `EST5EDT` (UTC-5) | **42 failed** | 92 passed |
| `UTC` | — | 92 passed |
| `Asia/Tokyo` | — | 92 passed |
| `America/New_York` | — | 92 passed |

注意 aware datetime 用 `==` 比的是**时刻**不是 tzinfo，所以单看 `to_local_aware` 的断言发现不了问题；真正暴露的是返回 naive 的 `to_local_naive`（naive 比的是墙钟）。

## 顺带发现的 flaky（非本批改动）

`tests/oas/ext/proc/test_bench_proc.py::test_every_skipped_pid_is_denied_in_the_c_layer` 首次全量跑红过一次，单跑 3/3 通过、复跑全量 2/2 绿。原因：先快照 `skipped = psutil_pids - fast_sweep()`，再逐个 `raw_cmdline(pid)` 断言抛 `OSError`；两次读之间进程可能退出，而该测试的 docstring 自己承认"进程可能在两次读之间消失"。属上一批 proc 遗留，本批未动。
