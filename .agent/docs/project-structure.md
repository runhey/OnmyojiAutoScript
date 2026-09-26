.
├─ oas/                          # 系统层：共享与后端领域
│  ├─ base/                      # 共享底座（filter/log_highlighter/timer/decorator/utils）
│  ├─ logger/                    # 日志领域（谁都用）
│  ├─ config/                    # 配置领域（backend 管写、script 读）
│  ├─ db/                        # sqlite 连接池
│  ├─ ocr/                       # 识别领域（算法+server 完整，不拆）
│  ├─ ext/                       # 通用工具箱
│  ├─ gui/                       # FluentApp 桌面壳
│  ├─ testing/                   # 测试控制层（时间/进程/文件系统 mock）
│  ├─ compat/                    # 迁移期转发壳（module.* → oas.* / script.*）
│  └─ backend/                   # 服务角色容器
│     ├─ webui/                  # FastAPI webui（module/server 迁入）
│     └─ manager/                # 进程管理（ScriptProcess/InstanceGuard/updater）
├─ script/                       # 干活层：worker 独有的都在这
│  ├─ misc/                      # 杂项底座（retry/protect/cBezier/grids/points）
│  ├─ device/                    # 设备控制（连接/截图/点击/scrcpy）
│  ├─ atom/                      # 游戏原子操作（RuleImage/Click/Ocr/Swipe）
│  ├─ map/                       # 地图网格
│  ├─ handler/                   # 敏感信息处理
│  ├─ notify/                    # 通知推送（onepush）
│  └─ team_flow/                 # 组队流程（host/player/mqtt）
├─ tasks/                        # 59 个游戏任务（原样不动）
│  └─ Component/                 # 任务共享组件（config_base/GeneralBuff...）
├─ assets/                       # 图片资源
├─ config/                       # 配置模板数据（与 oas/config 同名共存）
├─ deploy/                       # 部署配置
├─ tests/                        # 测试
├─ bin/                          # 二进制工具（adb 等）
├─ dev_tools/                    # 开发工具
├─ fluentui/                     # FluentUI 资源
└─ .agent/                       # agent 专用目录
   └─ docs/                      # 文档（agent + 人看）