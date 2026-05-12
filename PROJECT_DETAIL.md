# OnmyojiAutoScript (OAS) 项目详细文档

## 一、项目概述

**OnmyojiAutoScript**（简称 OAS）是一个基于 Python 的阴阳师手游自动化脚本工具，能够自动完成游戏中的日常任务、御魂副本、限时活动等操作，实现"一键托管"。

- **开发语言**: Python 3.10
- **运行平台**: Windows
- **开源协议**: GNU General Public License v3.0
- **项目来源**: 基于碧蓝航线脚本 [AzurLaneAutoScript](https://github.com/LmeSzinc/AzurLaneAutoScript) 开发
- **主仓库**: https://github.com/runhey/OnmyojiAutoScript

### 核心特性

| 特性 | 说明 |
|------|------|
| 全任务覆盖 | 日常、周常、寮活动、御魂副本、肝帝专属、限时活动等全面覆盖 |
| 任务调度系统 | 优异的任务调度系统，支持优先级、FIFO、过滤器等策略 |
| 无缝衔接 | 时间管理大师，无缝寄养，无缝执行任务 |
| 装饰可选 | 支持自定义庭院、主题等装饰 |
| AI百鬼夜行 | 利用AI智能撒豆子，模型包含所有式神 |
| 前后端分离 | 将前后端拆离，更加灵活，方便后续维护和扩展 |
| 多种GUI | 支持 QML 桌面端 GUI 和 Web 端界面 |
| 新OCR库 | 使用 ppocr-onnx，精度更高速度更快 |
| pydantic配置 | 使用 pydantic 优雅管理用户配置 |

---

## 二、项目目录结构总览

```
OnmyojiAutoScript/
├── script.py              # 脚本主入口（核心调度引擎）
├── gui.py                 # QML桌面GUI入口
├── server.py              # Web服务端入口（FastAPI）
├── requirements.txt       # Python依赖清单
├── requirements-in.txt    # Python依赖源文件
├── docker-compose.yaml    # Docker编排配置
├── LICENSE                # 开源许可证
├── README.md              # 项目说明
├── .gitignore             # Git忽略配置
├── .gitattributes         # Git属性配置
│
├── module/                # 核心模块（引擎层）
│   ├── atom/              # 原子操作层（图像/点击/滑动/OCR等）
│   ├── base/              # 基础工具（装饰器/过滤器/定时器/重试等）
│   ├── config/            # 配置管理系统
│   ├── daemon/            # 守护进程与基准测试
│   ├── device/            # 设备控制层（ADB/截图/操控/模拟器管理）
│   ├── gui/               # QML GUI模块
│   ├── handler/           # 处理器（敏感信息过滤等）
│   ├── map/               # 地图网格系统
│   ├── notify/            # 通知推送模块
│   ├── ocr/               # OCR文字识别模块
│   ├── server/            # Web服务端模块
│   ├── team_flow/         # 组队流程（MQTT通信）
│   ├── exception.py       # 全局异常定义
│   └── logger.py          # 日志系统
│
├── tasks/                 # 游戏任务实现层（业务层）
│   ├── Component/         # 通用组件（组队/召唤/换御魂/换号等）
│   ├── GameUi/            # 游戏UI导航系统
│   ├── GlobalGame/        # 全局游戏配置
│   ├── Script/            # 脚本全局配置
│   ├── Restart/           # 重启/登录任务
│   ├── GotoMain/          # 返回主界面
│   ├── ... (50+具体任务)  # 各类游戏自动化任务
│   └── Utils/             # 任务工具集
│
├── assets/                # 国际化资源
│   └── i18n/              # 多语言文件
│
├── bin/                   # 二进制资源
│   ├── hermit/            # Hermit APK
│   └── config/            # 默认配置模板
│
├── config/                # 运行时配置目录
│   ├── template.json      # 配置模板
│   └── findjade/          # 悬赏封印配置
│
├── deploy/                # 部署工具
│   ├── docker/            # Docker部署文件
│   ├── launcher/          # 启动器
│   └── *.py               # 安装器各组件
│
├── dev_tools/             # 开发者工具
│
├── fluentui/              # FluentUI QML组件库（C++）
│
└── .github/               # GitHub工作流与Issue模板
```

---

## 三、入口文件详解

### 3.1 [script.py](file:///c:/Users/76155/Desktop/mumuOAS/OnmyojiAutoScript/script.py) — 脚本主入口

这是整个自动化脚本的核心入口和调度引擎，定义了 `Script` 类，主要功能包括：

| 功能 | 说明 |
|------|------|
| `Script.__init__` | 初始化脚本，设置配置名、状态队列、失败记录等 |
| `Script.config` | 延迟加载配置对象（Config），使用 `cached_property` |
| `Script.device` | 延迟加载设备对象（Device），使用 `cached_property` |
| `Script.run(command)` | 执行指定任务，动态加载 `tasks/<command>/script_task.py` |
| `Script.loop()` | 主调度循环，不断获取下一个任务并执行 |
| `Script.get_next_task()` | 获取下一个待执行任务 |
| `Script.wait_until(future)` | 等待到指定时间，支持配置变更打断 |
| `Script.init_server(port)` | 初始化 zerorpc 服务，供 GUI 通信 |
| `Script.gui_*` | 一系列 GUI 交互方法（获取参数/菜单/任务列表/镜像等） |
| `Script.save_error_log()` | 保存错误日志和最近60张截图 |
| `Script.exception_handler(e)` | 异常处理器，如御魂溢出自动触发整理 |
| `Script._handle_wait_during_idle()` | 空闲等待策略（关游戏/回主页/关模拟器等） |

**任务调度流程**:
1. `loop()` 启动主调度循环
2. `get_next_task()` 从配置中获取下一个到期任务
3. 如果任务时间未到，根据策略等待（关游戏/回主页/关模拟器/原地等待）
4. 任务时间到了，`run(command)` 动态加载任务模块并执行
5. 执行完毕后回到步骤2

**异常处理层级**:
- `GameNotRunningError` → 自动调用 Restart
- `GameStuckError` / `GameTooManyClickError` → 保存错误日志 + 通知 + Restart
- `GamePageUnknownError` → 保存错误日志 + 通知 + Restart
- `ScriptError` → 通知 + 退出
- `RequestHumanTakeover` → 通知 + 退出

### 3.2 [gui.py](file:///c:/Users/76155/Desktop/mumuOAS/OnmyojiAutoScript/gui.py) — QML桌面GUI入口

基于 PySide6 + QML 的桌面图形界面入口：

1. 启动 OCR 服务
2. 创建 `FluentApp` 实例
3. 注入上下文对象：
   - `Add` — 添加配置上下文
   - `Setting` — 设置上下文
   - `ProcessManager` — 进程管理上下文
   - `Utils` — 工具上下文
4. 注册 QML 自定义类型：`PaintImage`、`RuleFile`
5. 启动 GUI 事件循环

### 3.3 [server.py](file:///c:/Users/76155/Desktop/mumuOAS/OnmyojiAutoScript/server.py) — Web服务端入口

基于 FastAPI + Uvicorn 的 Web 服务端入口：

1. 设置时区为北京时间（`Asia/Shanghai`）
2. 解析命令行参数（host/port/key/cdn/run）
3. 启动 OCR 服务
4. 运行 Uvicorn 服务器，加载 `module.server.app:fastapi_app`
5. 关闭时清理 OCR 服务

---

## 四、核心模块详解 (module/)

### 4.1 module/atom/ — 原子操作层

这是整个自动化框架的基础操作层，定义了所有与游戏交互的基本原子操作：

| 文件 | 类名 | 说明 |
|------|------|------|
| `image.py` | `RuleImage` | 图像匹配规则，支持模板匹配，包含 ROI 前置/后置区域、阈值、匹配方法等 |
| `click.py` | `RuleClick` | 点击规则，定义 ROI 区域，支持随机坐标点击、中心点点击、坐标移动等 |
| `long_click.py` | `RuleLongClick` | 长点击规则，继承自 RuleClick，增加长按持续时间参数 |
| `swipe.py` | `RuleSwipe` | 滑动规则，支持默认模式和向量模式，使用贝塞尔曲线模拟人手滑动轨迹 |
| `scroll.py` | `RuleScroll` | 滚动规则，用于列表滚动操作 |
| `ocr.py` | `RuleOcr` | OCR识别规则，整合多种OCR模式（全文/单字/数字/计数/时长/数量） |
| `list.py` | `RuleList` | 列表规则，用于管理列表类UI元素 |
| `image_grid.py` | `RuleImageGrid` | 图像网格规则，用于网格布局的图像匹配 |
| `gif.py` | `RuleGif` | GIF动画规则，用于匹配动态图像 |
| `animate.py` | `RuleAnimate` | 动画规则 |
| `cBezier.py` | `BezierTrajectory` | 贝塞尔曲线轨迹生成器，用于模拟人手滑动轨迹 |

**设计理念**: 每个原子操作都通过 JSON 配置文件定义参数（ROI区域、阈值等），`assets.py` 自动生成代码将 JSON 加载为 Python 对象，实现配置与代码分离。

### 4.2 module/base/ — 基础工具层

| 文件 | 说明 |
|------|------|
| `decorator.py` | 装饰器集合：`cached_property`（缓存属性）、`Config.when`（根据配置选择不同实现）、`del_cached_property`（删除缓存属性） |
| `filter.py` | 过滤器，用于任务调度中的任务过滤 |
| `retry.py` | 重试机制装饰器 |
| `timer.py` | 定时器，用于等待、超时检测等 |
| `protect.py` | 保护机制，防止异常操作 |
| `log_highlighter.py` | 日志高亮器 |
| `utils/__init__.py` | 工具函数集：图像裁剪、颜色检测、坐标转换等 |
| `utils/grids.py` | 网格系统工具 |
| `utils/points.py` | 点坐标工具 |
| `cBezier.py` | 贝塞尔曲线工具（备用） |

### 4.3 module/config/ — 配置管理系统

这是整个框架的配置核心，使用 pydantic 进行数据验证和管理：

| 文件 | 说明 |
|------|------|
| `config.py` | **核心配置类** `Config`，整合了配置更新、监控、菜单、模型、状态、调度器等。管理任务的启用/禁用、下次运行时间、优先级等 |
| `config_model.py` | `ConfigModel`，基于 pydantic 的配置数据模型，定义所有任务的配置结构 |
| `config_manual.py` | `ConfigManual`，手动配置，如调度器优先级等 |
| `config_menu.py` | `ConfigMenu`，GUI菜单配置 |
| `config_updater.py` | `ConfigUpdater`，配置文件版本更新/迁移 |
| `config_watcher.py` | `ConfigWatcher`，配置文件变更监控 |
| `config_state.py` | `ConfigState`，配置状态管理 |
| `config_modify.py` | 配置修改工具 |
| `config_server.py` | 服务器相关配置 |
| `scheduler.py` | `TaskScheduler`，任务调度器，支持三种调度策略：FILTER（过滤）、FIFO（先来后到）、PRIORITY（优先级） |
| `server.py` | 服务器配置 |
| `utils.py` | 配置工具函数 |
| `atomicwrites.py` | 原子写入，确保配置文件写入安全 |
| `argument/args.json` | 参数定义 |
| `argument/gui.yaml` | GUI布局配置 |
| `argument/menu.json` | 菜单定义 |
| `argument/task.yaml` | 任务定义 |
| `argument/default.yaml` | 默认配置 |
| `argument/override.yaml` | 覆盖配置 |
| `i18n/` | 国际化翻译文件（中文/英文） |

### 4.4 module/device/ — 设备控制层

这是与模拟器/设备交互的核心层，支持多种截图和控制方式：

| 文件 | 说明 |
|------|------|
| `device.py` | **核心设备类** `Device`，继承自 Platform + Screenshot + Control + AppControl，是所有设备操作的统一入口。自动选择最快的截图方法，处理模拟器启动等 |
| `connection.py` | ADB连接管理，处理设备连接、重连、端口转发等 |
| `connection_attr.py` | 连接属性，管理序列号、ADB地址等 |
| `control.py` | 控制操作统一入口，整合多种点击/长按方法（ADB/uiautomator2/minitouch/window_message/scrcpy） |
| `screenshot.py` | 截图操作统一入口，整合多种截图方法（ADB/ADB_nc/uiautomator2/DroidCast/scrcpy/window_background/nemu_ipc） |
| `app_control.py` | 应用控制，启动/停止游戏应用 |
| `emulator.py` | 模拟器管理，启动/停止模拟器 |
| `handle.py` | 窗口句柄管理 |
| `env.py` | 环境检测（是否Windows等） |
| `method/adb.py` | ADB方式截图/控制实现 |
| `method/droidcast.py` | DroidCast截图实现 |
| `method/minitouch.py` | Minitouch控制实现 |
| `method/nemu_ipc.py` | MuMu模拟器IPC截图实现 |
| `method/windows.py` | Windows窗口消息截图/控制实现 |
| `method/windows_impl.py` | Windows实现细节 |
| `method/uiautomator_2.py` | uiautomator2方式实现 |
| `method/utils.py` | 设备方法工具函数 |
| `method/scrcpy/` | Scrcpy截图/控制实现（含core/control/options/const） |
| `platform2/` | 平台相关实现（Windows模拟器检测/管理等） |
| `pkg_resources/` | 包资源补丁 |

**截图方法优先级**（自动基准测试选择最快的）:
1. `nemu_ipc` — MuMu模拟器IPC（最快）
2. `window_background` — Windows窗口后台截图
3. `DroidCast` / `DroidCast_raw` — DroidCast截图服务
4. `scrcpy` — Scrcpy截图
5. `uiautomator2` — uiautomator2截图
6. `ADB` / `ADB_nc` — ADB截图（最慢）

### 4.5 module/gui/ — QML GUI模块

基于 PySide6 + QML + FluentUI 的桌面图形界面：

| 文件/目录 | 说明 |
|-----------|------|
| `fluent_app.py` | `FluentApp`，GUI应用主类，初始化PySide6应用、QML引擎、翻译器、DPI缩放 |
| `Bridge.py` | QML与Python的桥接对象 |
| `utils.py` | GUI工具函数（管理员检测、工作路径等） |
| `qml_rcc.py` / `res_rcc.py` | QML/资源编译文件 |
| `qml_rcc.py` / `res_rcc.py` | QML/资源RC文件 |
| `context/add.py` | 添加配置上下文 |
| `context/settings.py` | 设置上下文 |
| `context/utils.py` | 上下文工具 |
| `context/process_manager.py` | 进程管理上下文 |
| `register_type/paint_image.py` | 自定义QML图片绘制类型 |
| `register_type/rule_file.py` | 自定义QML规则文件类型 |
| `process/script_process.py` | 脚本进程管理 |
| `qml/` | QML界面文件 |
| `qml/MainWindow.qml` | 主窗口 |
| `qml/app.qml` | 应用入口QML |
| `qml/Page/Home.qml` | 主页 |
| `qml/Page/ScriptView.qml` | 脚本视图 |
| `qml/Page/Update.qml` | 更新页面 |
| `qml/Page/O_Add.qml` | 添加配置页 |
| `qml/Page/O_Home.qml` | 主页对象 |
| `qml/Page/O_Settings.qml` | 设置对象 |
| `qml/Component/Add.qml` | 添加组件 |
| `qml/Component/Args.qml` | 参数组件 |
| `qml/Content/OcrRule.qml` | OCR规则内容 |
| `qml/Global/qmldir` | QML全局模块定义 |
| `res/` | GUI资源文件（图标等） |
| `FluentUI/qmldir` | FluentUI QML模块定义 |

### 4.6 module/server/ — Web服务端模块

基于 FastAPI 的 Web 服务端，提供 RESTful API 和 WebSocket 通信：

| 文件 | 说明 |
|------|------|
| `app.py` | FastAPI应用工厂，配置CORS、路由、生命周期、全局异常处理 |
| `home_router.py` | 首页路由 |
| `script_router.py` | 脚本操作路由 |
| `script_websocket.py` | WebSocket通信，实时推送脚本状态 |
| `script_process.py` | 脚本进程管理 |
| `main_manager.py` | 主管理器，管理脚本实例的启动/停止/重启 |
| `config_manager.py` | 配置管理器 |
| `config.py` | 服务端配置 |
| `setting.py` | 服务端设置，包含 `State` 全局状态 |
| `i18n.py` | 国际化支持 |
| `updater.py` | 更新管理 |

### 4.7 module/ocr/ — OCR文字识别模块

| 文件 | 说明 |
|------|------|
| `base_ocr.py` | `BaseCor` 基础OCR类，定义OCR模式枚举（FULL/SINGLE/DIGIT/DIGITCOUNTER/DURATION/QUANTITY）、ROI区域、关键词等 |
| `sub_ocr.py` | 各种OCR模式的子类实现：`Full`（全文）、`Single`（单字）、`Digit`（数字）、`DigitCounter`（数字计数）、`Duration`（时长）、`Quantity`（数量） |
| `ppocr.py` | PaddleOCR封装 |
| `rpc.py` | OCR RPC服务，支持独立OCR进程，使用 zerorpc 通信 |
| `models.py` | OCR模型管理 |
| `utils.py` | OCR工具函数 |

### 4.8 module/notify/ — 通知推送模块

| 文件 | 说明 |
|------|------|
| `notify.py` | `Notifier` 通知推送类，基于 onepush 库，支持多种推送渠道（如Server酱、Bark、Telegram等），配置通过 YAML 格式 |

### 4.9 module/team_flow/ — 组队流程模块

| 文件 | 说明 |
|------|------|
| `host.py` | `Host` 组队主机，继承 Mqtt + Player，管理组队玩家，处理上线通知/策略广播等 |
| `player.py` | `Player` 玩家信息 |
| `task.py` | `Task` 组队任务 |
| `mqtt.py` | MQTT通信封装，用于组队玩家间的实时通信 |
| `mqtt_test.py` | MQTT测试 |

### 4.10 module/daemon/ — 守护进程

| 文件 | 说明 |
|------|------|
| `daemon_base.py` | 守护进程基类 |
| `benchmark.py` | `Benchmark` 基准测试，自动测试各截图/控制方法的性能，选择最优方案 |

### 4.11 module/handler/ — 处理器

| 文件 | 说明 |
|------|------|
| `sensitive_info.py` | 敏感信息处理器，过滤截图和日志中的敏感路径信息 |

### 4.12 module/map/ — 地图系统

| 文件 | 说明 |
|------|------|
| `map_grids.py` | `SelectedGrids` 地图网格选择系统 |

### 4.13 module/exception.py — 全局异常定义

| 异常类 | 说明 |
|--------|------|
| `CampaignEnd` | 战役结束 |
| `MapDetectionError` | 地图检测错误 |
| `ScriptError` | 脚本错误（开发者问题） |
| `ScriptEnd` | 脚本正常结束 |
| `GameStuckError` | 游戏卡住 |
| `GameBugError` | 游戏客户端Bug |
| `GameTooManyClickError` | 点击次数过多 |
| `EmulatorNotRunningError` | 模拟器未运行 |
| `GameNotRunningError` | 游戏未运行 |
| `GamePageUnknownError` | 游戏页面未知 |
| `RequestHumanTakeover` | 请求人工接管（严重错误） |
| `TaskEnd` | 任务结束 |

### 4.14 module/logger.py — 日志系统

基于 `rich` 库的日志系统，支持：
- 彩色控制台输出
- 文件日志记录
- 日志自动清理（默认保留7天）
- 错误日志单独保存

---

## 五、任务系统详解 (tasks/)

### 5.1 任务目录结构规范

每个任务目录遵循统一的结构：

```
tasks/<TaskName>/
├── script_task.py    # 任务主逻辑（必须），定义 ScriptTask 类
├── config.py         # 任务配置（pydantic模型），定义用户可配置参数
├── assets.py         # 资源定义（自动生成），将JSON资源加载为Python对象
├── res/              # 资源文件目录
│   ├── image.json    # 图像匹配规则
│   ├── click.json    # 点击区域规则
│   ├── ocr.json      # OCR识别规则
│   ├── swipe.json    # 滑动规则
│   ├── list.json     # 列表规则
│   └── *.png         # 模板图片
└── page.py           # 页面导航（部分任务有）
```

### 5.2 任务列表

#### 日常任务类

| 任务目录 | 功能说明 |
|----------|----------|
| `WantedQuests` | 悬赏封印 |
| `KekkaiUtilize` | 结界卡使用/蹭卡 |
| `KekkaiActivation` | 结界上卡 |
| `DailyTrifles` | 每日小杂事（签到、商店、好感度等） |
| `Pets` | 小猫咪喂养 |
| `GoldYoukai` | 金币妖怪 |
| `ExperienceYoukai` | 经验妖怪 |
| `Nian` | 年兽 |
| `Delegation` | 委派任务 |
| `SoulsTidy` | 御魂整理 |
| `DemonEncounter` | 封魔（含答题数据） |
| `DemonRetreat` | 退治 |

#### 每周任务类

| 任务目录 | 功能说明 |
|----------|----------|
| `WeeklyTrifles` | 每周小杂事（秘闻竞速、区域boss、破符等） |
| `MysteryShop` | 神秘商店 |
| `RichMan` | 搜刮商店/神社 |
| `Duel` | 斗技 |
| `MetaDemon` | 超鬼王 |

#### 阴阳寮类

| 任务目录 | 功能说明 |
|----------|----------|
| `Dokan` | 道馆 |
| `RyouToppa` | 寮突破 |
| `RealmRaid` | 结界突破 |
| `CollectiveMissions` | 集体任务 |
| `GuildActivityMonitor` | 寮活动监控 |

#### 御魂副本类

| 任务目录 | 功能说明 |
|----------|----------|
| `Orochi` | 八岐大蛇（御魂） |
| `OrochiMoans` | 业原火 |
| `FallenSun` | 日轮之城 |
| `EternitySea` | 永生之海 |
| `SixRealms` | 六道之门 |
| `EvoZone` | 觉醒副本 |

#### 肝帝专属类

| 任务目录 | 功能说明 |
|----------|----------|
| `Exploration` | 探索（含solo单人模式、highlight高亮识别） |
| `BondlingFairyland` | 契灵之境 |
| `Sougenbi` | 御灵 |
| `AreaBoss` | 地鬼 |
| `Hyakkiyakou` | 百鬼夜行（AI撒豆） |
| `FindJade` | 找勾玉 |

#### 限时活动类

| 任务目录 | 功能说明 |
|----------|----------|
| `ActivityShikigami` | 式神爬塔活动 |
| `AbyssShadows` | 深渊暗影 |
| `FloatParade` | 花车巡游 |
| `FrogBoss` | 蛙老板 |
| `DyeTrials` | 染色试炼 |
| `MemoryScrolls` | 记忆卷轴 |

#### 系统任务类

| 任务目录 | 功能说明 |
|----------|----------|
| `Restart` | 重启/登录游戏 |
| `GotoMain` | 返回主界面 |
| `GameUi` | 游戏UI导航系统（页面路由） |
| `GlobalGame` | 全局游戏操作 |
| `Script` | 脚本全局配置 |
| `Quiz` | 答题 |

#### 通用组件 (tasks/Component/)

| 组件目录 | 功能说明 |
|----------|----------|
| `GeneralBattle` | 通用战斗流程 |
| `GeneralRoom` | 通用房间操作 |
| `GeneralInvite` | 通用邀请操作 |
| `GeneralBuff` | 通用加成操作 |
| `SwitchSoul` | 换御魂 |
| `SwitchOnmyoji` | 换阴阳师 |
| `SwitchAccount` | 换号/登录/退出 |
| `Summon` | 召唤 |
| `Buy` | 购买操作 |
| `Costume` | 装饰/皮肤 |
| `CostumeShikigami` | 式神皮肤 |
| `ReplaceShikigami` | 替换式神 |
| `RightActivity` | 右侧活动入口 |
| `LootStatistics` | 掉落统计 |
| `config_base.py` | 组件配置基类 |
| `config_scheduler.py` | 调度器配置 |

---

## 六、部署与安装 (deploy/)

### 6.1 部署工具文件

| 文件 | 说明 |
|------|------|
| `installer.py` | `Installer` 安装器主类，整合 Git/Pip/ADB/FluentUI/进程管理，一键安装 |
| `config.py` | 部署配置管理 |
| `git.py` | Git管理器，处理Git安装和仓库克隆 |
| `pip.py` | Pip管理器，处理Python依赖安装 |
| `adb.py` | ADB管理器，处理ADB工具安装 |
| `emulator.py` | 模拟器管理 |
| `fluentui.py` | FluentUI管理器，处理QML组件编译 |
| `process.py` | 进程管理器，处理进程启停 |
| `patch.py` | 补丁和预检查 |
| `logger.py` | 部署日志 |
| `utils.py` | 部署工具函数 |

### 6.2 Docker部署

| 文件 | 说明 |
|------|------|
| `deploy/docker/Dockerfile` | Docker镜像构建文件，基于 python:3.10-slim-bookworm，安装Git/ADB/依赖 |
| `deploy/docker/Dockerfile.cn` | 国内镜像版Dockerfile |
| `deploy/docker/requirements.txt` | Docker专用依赖 |
| `docker-compose.yaml` | Docker Compose编排配置，映射目录和端口 |

### 6.3 启动器

| 文件 | 说明 |
|------|------|
| `deploy/launcher/oas-gui.bat` | Windows GUI启动批处理 |
| `deploy/launcher/logo.ico` | 启动器图标 |

---

## 七、开发者工具 (dev_tools/)

| 文件 | 说明 |
|------|------|
| `assets_extract.py` | **资源提取器**，自动扫描 tasks/ 下所有 JSON 资源文件，生成对应的 `assets.py`，将 JSON 规则转换为 RuleImage/RuleClick/RuleOcr 等 Python 对象 |
| `template_update.py` | **模板更新器**，生成/更新 `config/template.json` 配置模板 |
| `get_images.py` | **截图工具**，基于 BaseTask，连续截图保存到 log/temp/ 目录，用于开发时获取模板图片 |
| `decorator.py` | 开发用装饰器 |
| `generate_requirements.py` | 依赖生成工具 |

---

## 八、FluentUI组件库 (fluentui/)

这是一个独立的 C++ Qt QML 组件库，提供 Fluent Design 风格的 UI 组件：

| 目录/文件 | 说明 |
|-----------|------|
| `CMakeLists.txt` | CMake构建配置 |
| `src/FluApp.cpp/h` | FluentUI应用管理 |
| `src/FluColors.cpp/h` | 颜色系统 |
| `src/FluColorSet.cpp/h` | 颜色集合 |
| `src/FluTheme.cpp/h` | 主题管理（亮色/暗色） |
| `src/FluTextStyle.cpp/h` | 文本样式 |
| `src/FluTools.cpp/h` | 工具集 |
| `src/FluRegister.cpp/h` | QML注册器 |
| `src/WindowHelper.cpp/h` | 窗口辅助 |
| `src/NativeEventFilter.h` | 原生事件过滤器 |
| `src/Def.cpp/h` | 基础定义 |
| `example/` | 示例应用 |
| `doc/preview/` | 组件预览图 |

---

## 九、配置与资源文件

### 9.1 国际化 (assets/i18n/)

| 文件 | 说明 |
|------|------|
| `zh-CN.json` | 简体中文翻译 |
| `en-US.json` | 英文翻译 |

### 9.2 二进制资源 (bin/)

| 文件 | 说明 |
|------|------|
| `hermit/hermit.apk` | Hermit无障碍服务APK |
| `config/template.json` | 默认配置模板 |
| `config/findjade/find_jade.json` | 悬赏封印配置数据 |

### 9.3 运行时配置 (config/)

| 文件 | 说明 |
|------|------|
| `template.json` | 配置模板（由 dev_tools/template_update.py 生成） |
| `findjade/find_jade.json` | 悬赏封印查找配置 |

### 9.4 GitHub工作流 (.github/)

| 文件 | 说明 |
|------|------|
| `workflows/auto-create-pr.yaml` | 自动创建PR |
| `workflows/github-mirror.yml` | GitHub镜像同步 |
| `workflows/issue-handle-*.lock.yml` | Issue自动处理工作流 |
| `workflows/pr-review-*.lock.yml` | PR审查工作流 |
| `workflows/tools/extract_tasks_i18n.py` | 提取任务国际化文本 |
| `ISSUE_TEMPLATE/` | Issue模板（Bug/功能请求/问题/其他） |
| `aw/actions-lock.json` | Actions锁定配置 |

---

## 十、核心依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| `pydantic` | 2.10.0 | 配置数据模型与验证 |
| `opencv-python` | 4.7.0.72 | 图像处理与模板匹配 |
| `ppocr-onnx` | 0.0.3.9 | OCR文字识别（基于PaddleOCR + ONNX） |
| `onnxruntime` | 1.16.3 | ONNX模型推理引擎 |
| `uiautomator2` | 2.16.17 | Android UI自动化 |
| `adbutils` | 0.11.0 | ADB工具封装 |
| `fastapi` | 0.104.1 | Web服务框架 |
| `uvicorn` | 0.38.0 | ASGI服务器 |
| `zerorpc` | 0.6.3 | 进程间RPC通信（GUI与脚本） |
| `PySide6` | — | Qt QML桌面GUI框架 |
| `paho-mqtt` | 1.6.1 | MQTT通信（组队功能） |
| `onepush` | 1.3.0 | 多渠道消息推送 |
| `frida` | 17.6.2 | 动态插桩工具 |
| `rich` | 13.3.5 | 终端美化输出 |
| `numpy` | 1.24.3 | 数值计算 |
| `inflection` | 0.5.1 | 命名转换（驼峰/下划线） |
| `cn2an` | 0.5.23 | 中文数字转阿拉伯数字 |
| `psutil` | 6.1.1 | 进程管理 |
| `pywin32` | 306 | Windows API调用 |

---

## 十一、架构设计总结

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    用户界面层                         │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  QML GUI     │  │  Web Server  │                 │
│  │  (PySide6)   │  │  (FastAPI)   │                 │
│  └──────┬───────┘  └──────┬───────┘                 │
│         │ zerorpc          │ HTTP/WS                  │
├─────────┼──────────────────┼─────────────────────────┤
│         ▼                  ▼                          │
│  ┌──────────────────────────────────────┐            │
│  │        Script (调度引擎)              │            │
│  │  - 任务调度循环                       │            │
│  │  - 异常处理与恢复                     │            │
│  │  - 空闲等待策略                       │            │
│  └──────────┬───────────────────────────┘            │
│             │                                         │
├─────────────┼─────────────────────────────────────────┤
│             ▼                                         │
│  ┌──────────────────────────────────────┐            │
│  │        Config (配置管理)              │            │
│  │  - pydantic数据模型                   │            │
│  │  - 任务调度器                         │            │
│  │  - 配置监控与热更新                    │            │
│  └──────────┬───────────────────────────┘            │
│             │                                         │
├─────────────┼─────────────────────────────────────────┤
│             ▼                                         │
│  ┌──────────────────────────────────────┐            │
│  │        Device (设备控制)              │            │
│  │  - 截图 (ADB/DroidCast/scrcpy/nemu)  │            │
│  │  - 控制 (ADB/minitouch/window/scrcpy)│            │
│  │  - 模拟器管理                         │            │
│  └──────────┬───────────────────────────┘            │
│             │                                         │
├─────────────┼─────────────────────────────────────────┤
│             ▼                                         │
│  ┌──────────────────────────────────────┐            │
│  │        Atom (原子操作)                │            │
│  │  - RuleImage (图像匹配)               │            │
│  │  - RuleClick (点击)                   │            │
│  │  - RuleSwipe (滑动)                   │            │
│  │  - RuleOcr (文字识别)                 │            │
│  └──────────┬───────────────────────────┘            │
│             │                                         │
├─────────────┼─────────────────────────────────────────┤
│             ▼                                         │
│  ┌──────────────────────────────────────┐            │
│  │        Tasks (游戏任务)               │            │
│  │  - 50+ 具体任务实现                    │            │
│  │  - Component 通用组件                  │            │
│  │  - GameUi 页面导航                     │            │
│  └──────────────────────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

### 关键设计模式

1. **配置驱动**: 所有任务参数、图像匹配规则、OCR规则等均通过 JSON/YAML 配置，代码与数据分离
2. **自动生成**: `assets.py` 由 `dev_tools/assets_extract.py` 自动生成，减少手动维护
3. **策略模式**: 截图方法、控制方法、调度策略等均可配置切换
4. **多态继承**: Device 类通过多继承组合不同功能（Platform + Screenshot + Control + AppControl）
5. **异常恢复**: 完善的异常处理层级，大部分异常可自动恢复（重启游戏/重启模拟器）
6. **进程隔离**: GUI进程与脚本进程分离，通过 zerorpc/WebSocket 通信
7. **热更新**: 配置文件变更监控，支持运行时修改配置

---

## 十二、运行方式

### 方式一：GUI模式
```bash
python gui.py
```
启动 PySide6 QML 桌面界面，通过图形界面管理配置和启动脚本。

### 方式二：Web服务模式
```bash
python server.py
```
启动 FastAPI Web 服务，通过浏览器管理配置和启动脚本。

### 方式三：Docker模式
```bash
docker-compose up
```
在 Docker 容器中运行 Web 服务模式。

### 方式四：脚本模式
```bash
python script.py
```
直接运行脚本调度引擎（通常由 GUI/Web 服务调用）。
