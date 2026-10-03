# base/op 迁移

`alasio/base/op/` 5 文件 → `script/misc/op/`，逐字节一致，相对导入不变，零 `alasio.*`/numpy。

| 文件 | 行 | OAS 对应 | 结论 |
|---|---|---|---|
| `area.py` `Area`/`Point` | 915 | `utils/points.py` `Points`/`Lines` | 无同名类型，直搬 |
| `color.py` `RGB` | 29 | — | 直搬 |
| `rng.py` | 69 | `utils/utils.py` 2 函数 | 见下 |
| `slist.py` `Slist` | 199 | `utils/grids.py` `SelectedGrids` | 同类改名，OAS 0 调用方 |

## 撞名
- `random_normal_distribution_int`：Alasio 用 `random.randint(a,b)` 闭区间且先 `round(a/b)`，OAS 原用 `np.random.randint` 左闭右开。**已把 `oas/base/utils/utils.py` 对齐 Alasio**。
- `random_rectangle_point`：纯委托，随上。
- `random_id`：与 `oas/ext/path/atomic.py` 的无参版同名，不同函数。
- `random_friendly_id`：无对应。

测试 `tests/script/misc/op/` 5 模块 125 passed。
