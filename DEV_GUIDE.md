# OAS 二次开发指南（开发要点与踩坑记录）

> 本文档沉淀实际开发中踩过的坑和验证过的做法。**开发新任务 / 改动现有任务前，先通读本文和
> [I18N_GUIDE.md](./I18N_GUIDE.md)，再看目标任务的 README.md**，避免重复踩坑。
> 每次开发结束后，把新的坑和结论补回本文对应章节。

## 目录

1. [新增一个任务的完整清单](#1-新增一个任务的完整清单)
2. [国际化：翻译必须写进两张表](#2-国际化翻译必须写进两张表)
3. [图片素材规范与验证](#3-图片素材规范与验证)
4. [页面注册与导航](#4-页面注册与导航)
5. [退出界面：粉色叉的检测和运用](#5-退出界面粉色叉的检测和运用)
6. [弹窗与原界面 UI 同时出现](#6-弹窗与原界面-ui-同时出现)
7. [长等待与设备卡死检测](#7-长等待与设备卡死检测)
8. [点击无响应的检测与重试](#8-点击无响应的检测与重试)
9. [战斗流程复用 GeneralBattle](#9-战斗流程复用-generalbattle)
10. [切换御魂](#10-切换御魂)
11. [调试技巧](#11-调试技巧)
12. [Git 工作流注意事项](#12-git-工作流注意事项)
13. [狭间暗域：集结等待与战斗提前结束](#13-狭间暗域集结等待与战斗提前结束)

---

## 1. 新增一个任务的完整清单

以 `tasks/XianShiYaoYue/` 为例，**缺一步就可能不生效**：

| 步骤 | 文件 | 说明 |
|---|---|---|
| 1 | `tasks/<TaskName>/config.py` | ConfigBase 子类，含 `scheduler: Scheduler` |
| 2 | `tasks/<TaskName>/script_task.py` | 必须含 `ScriptTask` 类，`script.py` 按 `tasks/<TaskName>/script_task.py` 动态加载 |
| 3 | `tasks/<TaskName>/assets.py` | 图片/OCR/点击资产（见第 3 节） |
| 4 | `tasks/<TaskName>/page.py` | 页面注册（可选，GameUi 会自动加载所有 page.py） |
| 5 | `module/config/config_model.py` | import + `Field(default_factory=...)` 注册 |
| 6 | `module/config/config_menu.py` | 加进 UI 分组（如 `Activity Task`） |
| 7 | **`module/config/config_manual.py` `SCHEDULER_PRIORITY`** | **最易漏！** 调度器按此表过滤待办队列，不在表里的任务 enable 后也会被直接丢弃（不进队列、不报错、不拉起） |
| 8 | `assets/i18n/zh-CN.json` + `module/config/i18n/zh-CN.json` | 两张翻译表（见第 2 节） |
| 9 | `tasks/<TaskName>/README.md` | 记录流程与特殊处理 |

验证调度是否生效（本地即可复现）：

```bash
./toolkit/python.exe -c "
from module.config.config import Config
c = Config('oas1')
c.update_scheduler()
print([f.command for f in c.pending_task])"
```

## 2. 国际化：翻译必须写进两张表

详见 [I18N_GUIDE.md](./I18N_GUIDE.md)。要点：

- `assets/i18n/zh-CN.json`：**附加翻译表**，oasx 界面显示中文的关键，不会被 GUI 回写覆盖
- `module/config/i18n/zh-CN.json`：全量主表，服务 QML 界面 / 通知标题 / 翻译编辑器回写
- **只加一张表是不够的**（百鬼夜行和现世妖约都踩过）
- 主表会被运行中的 GUI 回写覆盖（手工加的键会消失），这是正常现象，别在主表里找补——
  以附加表为准；后端 `_translate_text` 已改为按 mtime 热加载，改完无需重启后端
- 字段 label 由前端用「字段名 + 自己的翻译表」渲染，**后端下发的 title 前端不一定采用**；
  `config_model.py` 的 `merge_value` 里已加 pydantic 自动 title 的兜底翻译

## 3. 图片素材规范与验证

- 截图分辨率必须 1280x720；从用户提供的截图裁模板时，**必须避开截图上的标注框**
  （红圈/蓝框/绿框/白框），宁可裁小一点
- 模板匹配对缩放敏感：参考截图和实际截图的元素比例不同就不能用（如现世祝福卡片
  特写图与商店内尺寸不同，改用 OCR keyword）
- **同一元素在不同状态/账号下外观不同时，一个模板不够**，实测过的例子：
  - 左侧"活动"灯笼：活动页金色 / 商店页灰暗 → 两个模板都挂（page link 支持传 list）
  - 庭院"线下庆典"入口：动态立绘 + 位置随账号右栏图标数浮动 → 多个猫样式模板 +
    整个右栏做 roiBack（复用 FloatParade `fp_access` 的 `(1051,101,210,472)` 模式）
- **新模板必须验证**：对来源截图匹配得分应为 1.0；同时找一张"不该匹配"的截图测误报。
  注意测试时图片要转成 RGB（运行时设备截图是 RGB，`cv2.imread` 是 BGR，直接测会假阴性）
- OCR（RuleOcr）比模板更适合文字类检测，但**注意文案位置会随内容变化**
  （如排队横幅数字居中排版，固定 ROI 会读空），存在性检测优先用固定位置的元素
- **固定 roi（roi_back=roi_front）的文字横幅模板一碰就碎**：横幅是居中排版，
  随计时文字宽度/界面状态有 2~4px 漂移，固定 roi 下 matchTemplate 得分直接从 0.9+ 掉到 0.3x，
  运行时表现为"永远识别不到"（2026-09-27 狭间"集结中/进攻中"实测 0.35/0.26 → 放宽 roi_back 后 0.92/0.94）。
  对策：roi_back 放宽为覆盖横幅整个区域的搜索区（如 `(420,50,460,55)`），让匹配自己定位；
  离线验证时先用宽区 matchTemplate 打印真实坐标与得分再定 roi。
  注意用户聊天转存的截图常被裁掉几个像素（1280x720 → 1276x718），对这类截图测"固定 roi 模板"必然假阴性，
  结论要以宽区得分为准；右栏按钮等静态元素不会漂移，可以继续用固定 roi

## 4. 页面注册与导航

- 页面定义在任务的 `page.py`，`Page(check)` + `page.link(button, destination)` 双向挂链接；
  `GameUi` 初始化时自动 import 所有 `tasks/**/page.py`
- `link` 的 button 支持传 list（同一跳转有多个外观时全部挂上）
- 从任意界面恢复到目标页：`self.ui_goto(page_xxx)`；页面未注册/识别不了时框架的
  `try_close_unknown_page` 会自动尝试关闭按钮（`ui_close` 列表）

## 5. 退出界面：粉色叉的检测和运用

- 十周年现世妖约的活动页/商店页**必须先点右上角粉色叉再点左上角黄色返回**，
  叉不点则返回按钮无效
- **粉叉可直接复用通用资产 `I_UI_BACK_RED`**（GlobalGame），无需新裁模板——
  遇到"疑似新按钮"先在现有资产里找（红色关闭、确认框、刷新键等通用样式大概率已有），
  找不到再裁新图
- 退出逻辑用循环直到 `I_CHECK_MAIN`：先叉后返回，参见 `XianShiYaoYue/script_task.py` 的 `_exit_to_main()`

## 6. 弹窗与原界面 UI 同时出现

**踩坑实例**：点"组队挑战"后弹出居中的"队伍公开权限"弹窗，弹窗**不遮挡**右下角的
组队挑战按钮。原写法"点组队挑战 → 等按钮消失 → 再处理弹窗"形成死循环：
按钮永远可见，弹窗处理代码永远执行不到，15 秒后误判卡死。

正确做法：**等待条件不能建立在"会被弹窗遮挡关系欺骗"的目标上**，改用状态机同时检测
多个目标，弹窗优先处理：

```python
while 1:
    self.screenshot()
    popup = self.appear(I_CREATE)          # 弹窗元素
    button = self.appear(I_TEAM_CHALLENGE) # 原界面元素
    if not popup and not button:
        break                              # 两者都消失才算完成
    if popup:
        ...                                # 弹窗优先
    elif button:
        ...                                # 无弹窗才点原按钮
```

同类问题：排队横幅出现在屏幕上方且带 X 按钮——**那个 X 是取消排队，绝不能点**；
把横幅 X 模板当作"排队中"的存在检测（位置固定，比 OCR 数字稳）。

**别假设"确认弹窗"一定有确定/取消**（2026-09-27 现世妖约买祝福踩坑）：点商品弹的
详情弹窗，购买交互是底部**金色价格按钮本身**（勾玉图标+价格），没有确定/取消对——
用 I_UI_CONFIRM 系列等确认会 6 秒零点击落空，随后二次 OCR 还会把"被弹窗挡住的
卡片"读空，误判成"已购买"。对策：拿到真实弹窗截图再裁模板；等不到预期按钮就
显式关闭弹窗重试，别让"读空"顺延成误判。

## 7. 长等待与设备卡死检测

- 设备层卡死检测：60 秒无点击动作 → `GameStuckError('Wait too long')` → 任务重启；
  `stuck_record_add('BATTLE_STATUS_S')` 可豁免短计时，但 300 秒长计时仍会触发
- **匹配/排队等长等待场景，循环每轮调用 `self.device.stuck_record_clear()`**，
  超时改由循环自己的 Timer 管理（参考 `_match_and_battle`）：
  - 检测到排队横幅 → 重置等待计时，继续等（人数 10 分钟无变化只告警不重启）
  - 横幅消失后才启用有限等待窗（180 秒）
- 战斗内长等待参考 `GeneralBattle.battle_wait`（stuck_record_add + 定期随机点击）

## 8. 点击无响应的检测与重试

每个关键点击步骤都要回答三个问题：怎么确认点成功了？没成功多久重试？重试几次后怎么办？

- 跳转型点击：`ui_click(click, stop=目标页元素, interval=1.5, timeout=20)` 自带重试；
  返回 False 即失败
- 状态型点击（点了会消失的按钮）：循环 `appear(按钮)` + `click(interval=2)`，直到消失
- 重试耗尽的处置要区分场景：
  - **可能是正常业务结束**（如挑战次数用尽导致点击无响应）→ 先做业务检测
    （OCR 次数），用尽则抛业务异常（`BattleCountOut`）判定任务完成，正常收尾
  - 确实异常 → `raise GameStuckError`，由 script.py 统一走重启恢复
- 有次数限制的活动，**轮次开始前 + 点击无响应时**都要检查剩余次数
- **坑：判定"元素不存在"之前先等 UI 异步加载完**（2026-09-25 悬赏食梦貘被跳过的根因）：
  悬赏详情页的"追踪"按钮先渲染、"前往"目的地列表等服务器异步返回（同一次运行里
  有 1.4s+ 才就绪的实例），点开详情后立刻 `appear(I_GOTO_1)` 会误判成
  "未解锁的神秘任务"而跳过整个悬赏。已修：改用
  `wait_until_appear(I_GOTO_1, wait_time=3)`，超时才走跳过分支。
  任何"点开面板 → 立刻检查里面某个元素"的写法都要留 2~3 秒加载窗，
  尤其当"元素缺失"会触发跳过/放弃分支时
- **坑：清零 `click_record` 规避 `GameTooManyClickError` 时，计数必须按真实点击、且循环必须有 Timer 总上限**
  （2026-09-26 悬赏秘闻聊天循环的根因）：合法的连点场景（如秘闻长对话）确实需要绕开
  "同按钮 15 窗口内 ≥10 次即抛"的保护，但有两个前提——
  ① `self.click(btn, interval=x)` 被 interval 拦截时**返回 False 不实际点击**（不抛错），
  计数器必须用返回值判断，否则循环每 ~0.2s 迭代一次会把"6 次清零"变成"每 2 秒清零"，
  保护被整体废掉；② 连点会不断 `stuck_record_clear()` 重置 60 秒卡死计时，
  **点击无效目标时 GameStuckError 永远不会触发**，循环必须自带 Timer（参考
  `WantedQuests.secret()`：Timer(60) 超时 raise GameStuckError，6 次真实点击才清零一次）

## 9. 战斗流程复用 GeneralBattle

- 通用战斗一律 `self.run_general_battle(config=self.conf.general_battle)`：
  自动处理准备按钮、预设队伍、战斗等待、胜利/失败判定、结算点击（点一次确认跳转，
  不连点）
- 组队/协战战斗同样适用：进入战斗准备界面后与普通战斗一致
- `current_count` 由 run_general_battle 自增，第一场才会执行预设队伍切换
- 排队/邀请等组队前置流程需要自己写（参考 `_match_and_battle` 的状态机）
- **坑：挑战类战斗没有准备阶段，预设队伍流程必须能退出**（2026-09-26 悬赏卡死无限重启的根因）：
  式神挑战点"挑战"后直接开战，但战斗加载过渡期 `is_in_prepare` 会短暂命中，
  `switch_preset_team` 随之运行；战斗真正开始后左下角预设按钮的位置变成**手动/自动切换按钮**，
  OCR 循环点过去一下就把战斗切成手动（该状态账号级记忆，重启后依旧手动），
  而循环关键字是'预设'永远匹配不上、又没有超时 → 无点击死循环 60 秒 GameStuckError →
  重启 → 重跑同一悬赏 → 再卡死，无限循环。
  已修：循环加 15 秒 Timer 超时直接放弃预设；循环内检测 `O_BATTLE_HAND`/`O_BATTLE_AUTO`
  （战斗已开打）立即 return，让 `battle_before` 走到 `ensure_auto_battle` 切回自动。
  新写战斗前置流程时同样要回答"这个循环最坏情况怎么退出"

## 10. 切换御魂

- 复用 `SwitchSoul` 组件：`ui_goto(page_shikigami_records)` →
  `run_switch_soul('组,队')` 或 `run_switch_soul_by_name(组名, 队名)` → 回主界面
- 配置用 `tasks/Component/SwitchSoul/switch_soul_config.py` 的 `SwitchSoulConfig`
- 切换御魂后可能触发御魂不一致提示，`battle_before` 内已自动处理

## 11. 调试技巧

- **远端抓图**：`adb -s <serial> exec-out screencap -p > xxx.png`（MuMu 多开用
  adb connect 127.0.0.1:16xxx 对应端口），排查"卡在哪"先抓图再看日志
- **验证 i18n 下发**：`ConfigModel().script_task('TaskName')` 直接得到前端会收到的
  结构化数据，检查 title/description 是否已翻译
- **验证模板**：见第 3 节，注意 RGB/BGR
- **验证资产/导入**：`./toolkit/python.exe -m py_compile ...` +
  `import tasks.<TaskName>.script_task`
- 日志里的 `WARNING ui_click timeout` / `Failed recognize ...` 是定位卡点的重要线索，
  通常意味着模板在该页面失配（先怀疑状态差异，再怀疑坐标）
- dev_tools 下临时调试文件用完及时删除

## 12. Git 工作流注意事项

- 分支 `Tokisaki` 跟踪 `fork/Tokisaki`（origin 是作者的 gitcode，不要动）
- **改动必须先 commit**：`update_tokisaki.bat` 更新时要做 rebase，未提交的改动会挡住
- 用户手工改动过的文件（如 `tasks/Hyakkiyakou/*`）提交时注意区分，不要混入无关变更

---

## 13. 狭间暗域：集结等待与战斗提前结束

- **别用"等待某横幅消失"判定阶段切换，要等正向信号**：寮活动监控拉起狭间时正处于集结期，
  旧写法 `wait_until_disappear(集结中)` 有两个失效方式——进图过渡动画期横幅尚未渲染（首帧就"消失"）、
  模板固定 roi 失配（见第 3 节）——都会导致集结中就开打、进攻连续失败。已改为 `wait_rally_finish()`：
  轮询顶部横幅出现"进攻中"（I_IS_ATTACK）才算集结结束；循环每轮 `stuck_record_clear()` 保活，
  15 分钟 Timer 兜底，超时走 `set_next_run(success=False)` 失败重试路径。
- **战斗可能因首领被其他寮友击败而提前结束**：无结算、直接退回集结地图（顶部横幅变"进攻中"，
  右下角"战报"按钮恢复可用）。智能战斗时间的傻等循环里加
  `I_ABYSS_NAVIGATION or I_IS_ATTACK` 双信号检测，提前 break 继续点战报找下一个目标。
- **战斗收尾一个循环处理三种状态**（`run_general_battle_back`）：
  ① 仍在战斗 → 点 I_EXIT + I_EXIT_ENSURE 退出；
  ② 结算残留 → 点 I_WIN 逐页推进（注意结算有多页，点一次 I_WIN 就 return 会把剩余页留给
  下一个 find_enemy 的无点击死循环，60 秒后误判卡死）；
  ③ 未知界面 → 盲点屏幕中央一下 → `sleep(2)` → 复查是否回到集结地图（结算/奖励页点击任意处可继续）。
  收尾循环必须有 Timer 总上限（120s），超时 `raise GameStuckError` 走重启恢复；
  盲点节奏 ≥2 秒/次，`click_record`（deque maxlen=15）的 GameTooManyClickError 保护仍兜得住

## 14. 对弈竞猜：活动改版模板失效与防重启时间驱动设计（2026-10-01）

- **活动 UI 改版后模板"集体失配"的特征**：任务进入页面后所有状态模板同时 miss、
  日志 `Waiting for set()` + 60 秒后 `GameStuckError` → 重启游戏 → next_run 已过又立刻
  重跑 → 反复重启。定位方法：拿报错截图对模板做**多尺度 matchTemplate**（0.7~1.4 步进 0.025），
  十周年对弈竞猜在 0.85 倍全中（0.99）→ 整套 UI 缩放了 15%，模板必须按新截图重裁。
  常见诱因：网易活动改版/换皮，旧 ROI 和旧阈值全部作废。
- **时间驱动型活动任务别依赖固定场次表**：用页面上的倒计时 OCR（注意 Duration 模式
  正则要求 H:MM:SS，"MM:SS" 会解析失败返回 None，改 Single 模式自己 parse）实推结算时刻，
  `set_next_run(task, target=绝对时刻)` 直接给调度器定目标；估错了下次到点会再校正，自愈。
- **休息/不可参与态要约到“下一个可操作窗口”而不是“下一场开场”**：2026-10-01 实测 8:33 休息
  被排到 10:03（下一场开场+3min），但下注窗口是 11:45（结算前 15 分钟），开场≠可操作；
  且场次表本身写错（首场实际 10:00 开）。改法：按结算时刻表推 `下一场结算 - before_end`，
  窗口已过就顺延到再下一场；开场+3min 只用于“进不了页面需要重试”的场景。
- **这类任务必须自带防重启**：主循环每轮 `stuck_record_clear()`（60 秒卡死保护交给任务自己的
  软超时 Timer 兜底，超时走 存截图+推送+改期 30 分钟，绝不 raise 卡死异常）；
  纯网络请求循环（如拉大神博主动态）同样要定期保活 + requests 全部带 timeout。
- **判"下注/购买类操作是否成功"要找不依赖新素材的判据**：如双鼓消失、页面离开原状态；
  弹窗内部按钮素材没到位时，宁可走失败路径推送通知，也不要盲点（涉及真实金币）。
- 相关文件：`tasks/FrogBoss/`（README 记录完整流程与待补素材清单）。
