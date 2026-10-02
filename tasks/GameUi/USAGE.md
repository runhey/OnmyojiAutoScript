# GameUi 使用说明

## 模块结构

- `game_ui.py`
  公开导出 `GameUi`、`NavigatorSession`、`Page`，供任务继续按旧导入路径使用。
- `page.py`
  公开导出 `Page`、`Transition`、组合 matcher、组合 action，以及所有全局页面定义。
- `common.py`
  共享类型与内部工具函数。
- `matcher.py`
  页面识别条件组合器。
- `action.py`
  页面跳转动作与 hook 动作组合器。
- `page_definition.py`
  `Page` 与 `Transition` 的核心定义。
- `registry.py`
  进程级静态页面注册表。
- `session.py`
  任务级导航 session，保存页面快照、边惩罚、局部未知页关闭规则。
- `navigator.py`
  `GameUi` 导航引擎实现。
- `default_pages.py`
  全局页面定义。

## 新版 Page 怎么定义

### 1. 最基础的页面

```python
from tasks.GameUi.page import Page
from tasks.SomeTask.assets import SomeTaskAssets

page_some_main = Page(SomeTaskAssets.I_CHECK_MAIN)
```

说明：

- 第一个参数是页面识别条件 `recognizer`
- 可以直接传 `RuleImage`、`RuleGif`、`RuleOcr`
- 不显式传 `category` 时，会根据文件路径自动推断
- `priority` 默认是 `50`，范围 `1-100`，值越大在多页面同时命中时越优先返回
- `tasks/GameUi` 下定义的页面默认分类为 `global`

### 1.1 页面优先级

```python
page_result = Page(
    SomeAssets.I_CHECK_RESULT,
    priority=70,
)
```

说明：

- `priority` 仅影响“多个页面在同一帧同时命中”时的返回顺序
- 系统会按 `priority` 降序判定；同优先级保持 session 注册顺序稳定
- 超出 `1-100` 时会自动 clamp，并输出 warning 日志
- 运行时修改 `session` 页面副本的 `priority`，不会污染全局注册表

### 2. 识别条件可以组合

```python
from tasks.GameUi.page import Page, any_of, all_of, not_

page_reward = Page(
    any_of(
        SomeAssets.I_REWARD_A,
        SomeAssets.I_REWARD_B,
    )
)
```

可用组合器：

- `any_of(...)`
  任一条件命中即可
- `all_of(...)`
  所有条件都命中才成功
- `not_(...)`
  对条件取反

### 3. 识别条件可以使用自定义函数

```python
def check_custom(task) -> bool:
    return task.appear(SomeAssets.I_CHECK_MAIN) and not task.appear(SomeAssets.I_DIALOG)


page_custom = Page(check_custom)
```

说明：

- 自定义函数会收到当前运行时的 `task`
- 可以直接调用当前任务对象上的所有公开方法
- 返回值必须是布尔值

### 4. 页面 hook

```python
page_main.add_enter_success_hooks(
    SomeAssets.I_CLOSE_DIALOG,
    lambda task: task.click(SomeAssets.C_SAFE_AREA, interval=0.5),
)
```

页面支持 4 个阶段：

- `on_enter_success`
  成功进入该页面后触发
- `on_enter_failure`
  尝试进入该页面失败后触发
- `on_leave_success`
  成功离开该页面后触发
- `on_leave_failure`
  尝试离开该页面失败后触发

可用写法：

- `page.add_enter_success_hooks(...)`
- `page.add_enter_failure_hooks(...)`
- `page.add_leave_success_hooks(...)`
- `page.add_leave_failure_hooks(...)`

旧版 `additional` 的语义，等价于新版 `on_enter_success`。

### 5. 页面跳转边

```python
page_main.connect(page_shop, SomeAssets.I_GOTO_SHOP, key="page_main->page_shop")
page_shop.connect(page_main, SomeAssets.I_BACK_Y, key="page_shop->page_main")
```

说明：

- `connect(destination, action, ...)` 用来声明一条有向边
- `action` 是执行跳转时的动作
- 推荐为边显式提供稳定的 `key`
- 可以为边单独定义四阶段 hook

### 6. 动作组合

```python
from tasks.GameUi.page import sequence, conditional_action

page_main.connect(
    page_event,
    sequence(SomeAssets.I_OPEN_PANEL, SomeAssets.I_GOTO_EVENT),
    key="page_main->page_event",
)

page_event.add_enter_success_hooks(
    conditional_action(SomeAssets.I_POPUP, SomeAssets.I_CLOSE_POPUP)
)
```

可用组合器：

- `sequence(...)`
  顺序执行多个动作
- `conditional_action(condition, action)`
  只有条件命中时才执行动作

## 页面分类规则

- `tasks/GameUi` 内定义的页面默认属于 `global`
- 其他任务的 `page.py` / `inner_page.py` 页面默认按任务目录名归类
- 导航到目标页面时：
  构图使用 `当前页面分类 + 目标页面分类 + global`
- 当前页面未知时：
  构图回退为 `目标页面分类 + global`
- 识别当前页时：
  使用 `当前任务分类 + 目标页面分类 + global`

这意味着：

- 全局页面可作为所有任务的公共中转页
- 不同任务页面不会在同一轮导航中互相污染

## 新公共方法

### `pages_in_category(category)`

```python
battle_pages = self.pages_in_category("battle")
```

说明：

- 返回当前 task session 内指定分类的页面副本列表
- 不会触发截图、识别或任何点击
- 调用方可以安全修改返回页面的 `priority` / `recognizer`

### `detect_page_in(*targets, include_global=True)`

```python
self.detect_page_in("battle")
self.detect_page_in("battle", "exploration")
self.detect_page_in("battle", include_global=False)
self.detect_page_in(page_battle_prepare, page_battle_result, include_global=False)
```

说明：

- `targets` 可以传分类字符串，也可以直接传 `Page`
- 使用与 `get_current_page()` 相同的“两帧稳定识别”逻辑
- 默认自动把 `global` 加入识别范围，便于识别意外弹回主页等全局页面
- 只传 `Page` 时，仅在这些显式页面副本中识别
- 传 `include_global=False` 时，只在显式给定分类内识别
- 多个候选同时命中时，同样按 `priority` 降序返回

## 动态页面怎么写

动态页面不要直接注册到全局表，必须只放在当前任务 session 中。

```python
from tasks.GameUi.page import Page

page_dynamic = self.navigator.add_page(
    Page(
        self.I_CHECK_DYNAMIC,
        key="page_dynamic",
        name="page_dynamic",
        register=False,
    )
)
```

说明：

- `register=False`
  表示不要进入全局 `PageRegistry`
- `self.navigator.add_page(...)`
  表示把该页面加入当前任务 session
- 动态页的跳转边也应该只连接到 session 页面对象

## 运行时改链怎么做

如果任务需要临时修改页面图，不要改全局定义，必须改当前 session 副本。

```python
page_main = self.navigator.resolve_page(pages.page_main)
page_records = self.navigator.resolve_page(pages.page_shikigami_records)

page_main.remove_transition(key="page_main->page_shikigami_records")
page_records.clear_transitions()
page_records.connect(page_main, self.I_BACK_Y, key="page_shikigami_records->page_main")
```

说明：

- `resolve_page(...)` 会把静态页面定义解析成当前任务 session 中的页面副本
- 所有运行时改链都只改 session，不会污染别的任务

## 未知页关闭规则怎么加

```python
self.navigator.add_unknown_closer(self.I_CUSTOM_CLOSE)
```

说明：

- 任务级规则会优先于全局默认规则执行
- 只在当前任务 session 生效
- 任务结束后自动失效

## goto_page 的流程是什么

`goto_page(destination)` 的执行流程如下：

1. 先把 `destination` 解析成当前任务 session 中的页面对象
2. 优先确认缓存的 `current_page` 是否仍然成立
3. 如果缓存页失效，则在允许分类集合里做两帧稳定识别
4. 如果当前页未知：
   - 先尝试 `close_unknown_pages()`
   - 成功则重置无进展超时计时器
   - 失败且超过超时则抛 `GamePageUnknownError`
5. 如果当前页就是目标页：
   - 再做一次两帧稳定确认
   - 成功后触发进入成功 hook，并打印到达日志
6. 如果当前页不是目标页：
   - 在 `当前页分类 + 目标分类 + global` 图中运行 Dijkstra
   - 计算代价 = 页面 cost + 边 cost + 边失败惩罚
7. 如果能构建路径：
   - 按最小总代价路径执行每一条边
   - 每次成功推进到下一页，都重置无进展超时
8. 如果某条边执行失败：
   - 触发页面/边的失败 hook
   - 给该边增加惩罚
   - 重新识别当前页并重新规划路径
   - 如果同一条边连续失败 3 次，则额外主动尝试一次 `close_unknown_pages()`
   - 主动关闭成功才重置无进展超时；关闭 miss 仍沿用原有惩罚、重规划和超时链路
9. 如果连续 `timeout` 秒没有任何有效进展：
   - 输出当前页、目标页、候选页命中结果、重复失败边、连续失败次数、边惩罚、未知页关闭历史等诊断日志
   - 抛出 `GamePageUnknownError`

## 页面判定规则

- 当前页识别：
  连续 2 帧命中才算成功
- 页面进入成功：
  连续 2 帧识别到目标页面才算成功
- 页面离开成功：
  以识别到下一页面为准，不是以“动作已经点击”为准

## 推荐写法

### 静态任务页面

```python
from tasks.GameUi.page import Page, page_main

page_my_task = Page(MyAssets.I_CHECK_MAIN)
page_main.connect(page_my_task, MyAssets.I_ENTER, key="page_main->page_my_task")
page_my_task.connect(page_main, MyAssets.I_BACK, key="page_my_task->page_main")
```

### 任务运行

```python
class ScriptTask(GameUi, MyAssets):
    def run(self):
        self.goto_page(page_my_task)
```

### 动态页 + 运行时改链

```python
class ScriptTask(GameUi, MyAssets):
    def before_run(self):
        self.page_dynamic = self.navigator.add_page(
            Page(self.I_CHECK_DYNAMIC, key="page_dynamic", name="page_dynamic", register=False)
        )
        page_main = self.navigator.resolve_page(pages.page_main)
        page_main.connect(self.page_dynamic, self.I_ENTER_DYNAMIC, key="page_main->page_dynamic")
```

## 注意事项

- 不要再使用旧接口：
  `ui_goto`、`ui_goto_page`、`ui_get_current_page`、`try_close_unknown_page`、`run_additional`
- 不要再直接操作旧运行时字段：
  `ui_current`、`ui_close`、`links`
- 动态页一定要使用 `register=False`
- 任务级改链一定要通过 `self.navigator.resolve_page(...)` 获取 session 页面后再修改
- 如果页面是临时弹层，优先写成进入成功 hook 或未知页关闭规则，不要把它误建成主导航页面
