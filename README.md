<div align="center">

# OnmyojiAutoScript

<br>

<div>
    <img alt="python" src="https://img.shields.io/badge/python-3.10-%233776AB?logo=python">
</div>
<div>
    <img alt="platform" src="https://img.shields.io/badge/platform-Windows-blueviolet">
</div>
<div>
    <img alt="license" src="https://img.shields.io/github/license/runhey/OnmyojiAutoScript">
    <img alt="GitHub repo size" src="https://img.shields.io/github/repo-size/runhey/OnmyojiAutoScript">
    <img alt="GitHub all releases" src="https://img.shields.io/github/downloads/runhey/OnmyojiAutoScript/total">
    <img alt="stars" src="https://img.shields.io/github/stars/runhey/OnmyojiAutoScript?style=social">
</div>
<br>

阴阳师自动化脚本 

一键托管


### [文档](https://runhey.github.io/OnmyojiAutoScript-website/)

#### 主仓库: [https://github.com/runhey/OnmyojiAutoScript](https://github.com/runhey/OnmyojiAutoScript)

</div>

阴阳师，作为一个手游，已经进入了生命周期的晚期。从现在到关服的这段时间里，请减少花费在阴阳师上的时间，把一切都交给 OAS。

## 功能 Features

- **日常任务**: 悬赏封印、小猫咪、小杂签到、金币妖怪、年兽、花合战、地鬼、封魔、御魂整理
- **每周相关**: 真蛇、秘闻竞速、神秘商店、搜刮商店、斗技、每周小杂事
- **阴阳寮**: 结界上卡、结界蹭卡、结界突破、寮突破、狩猎战、集体任务、道馆
- **御魂副本**: 八岐大蛇、业原火、日轮之城、永生之海、六道之门
- **肝帝专属**: 探索、契灵、御灵、觉醒副本、石距、百鬼夜行
- **限时活动**: 每期爬塔、超鬼王、对弈竞猜、花车巡游、智力答题

### 显著特点 
- **全部任务**: 你能想到的没有想到的都有，一条龙给你解放双手（该画饼画饼，该挖坑挖坑）
- **无缝衔接**: 时间管理大师，优异的任务调度系统，无缝寄养，无缝执行任务
- **装饰可选**: 全部初始皮肤是什么鬼，这里支持你喜欢的庭院、主题等等，[详细说明](https://github.com/runhey/OnmyojiAutoScript/issues/180)
- **百鬼夜行**: 利用AI来智能撒豆子，模型包含所有式神，[效果展示](https://runhey.github.io/OnmyojiAutoScript-website/docs/user-manual/hyakkiyakou)

## 许可证 LICENSE

This project is licensed under the GNU General Public License v3.0.

## 声明 Announcement
本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。
OAS is a free open source software, if you paid for OAS from any channel, please refund.
OAS 是一款免费开源软件，如果你在任何渠道付费购买了OAS，请退款。

## 关于 Alas
OAS 基于碧蓝航线脚本 [AzurLaneAutoScript](https://github.com/LmeSzinc/AzurLaneAutoScript) 开发，考虑到星穹铁道脚本 [StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot) 中所提及的问题，
OAS 在其基础上进行了如下优化：
- **调整设计架构**: 将前后端拆离出来更加灵活，方便后续的维护和扩展；优化代码架构使其减少同游戏耦合，更加通用。
- **搭建新的GUI**: 原先的方案过于臃肿，选用 [flutter](https://flutter.cn) 搭建一个全平台的界面端，界面更加舒适简洁
- **新的OCR库**: 跟随 [LmeSzinc](https://github.com/LmeSzinc) 的步伐， [ppocr-onnx](https://github.com/triwinds/ppocr-onnx) 更加简易使用，精度更高速度更快 
- **新的Assets管理**: 构建了一个新的Assets管理系统，更加方便的管理游戏资源如图片，文字，点击等等
- **配置文件 [pydantic](https://github.com/pydantic/pydantic) 化**: pydantic 可以更加优雅的管理用户配置

## 相关项目 Relative Repositories

- [Alas](https://github.com/LmeSzinc/AzurLaneAutoScript): 碧蓝航线的自动化脚本
- [SRC](https://github.com/LmeSzinc/StarRailCopilot): 星铁速溶茶，崩坏：星穹铁道脚本，基于下一代Alas框架。
- [OASX](https://github.com/runhey/OASX): 同 OAS 对接的全平台 GUI
- [NikkeAutoScript](https://github.com/megumiss/NIKKEAutoScript): 胜利女神：NIKKE 自动日常脚本
- [AAS](https://github.com/TheFunny/ArisuAutoSweeper): 蔚蓝档案自动化脚本
- [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights): 明日方舟小助手，全日常一键长草
- [FGO-py](https://github.com/hgjazhgj/FGO-py): 全自动免配置跨平台开箱即用的Fate/Grand Order助手
- [OAS-website](https://github.com/runhey/OnmyojiAutoScript-website): OAS 的文档网站，使用 [docusaurus](https://docusaurus.io/) 构建
- [ppocr-onnx](https://github.com/triwinds/ppocr-onnx): OCR 库，基于 onnxruntime 和 PaddleOCR
- [gurs](https://github.com/2833844911/gurs): 基于赛贝尔曲线模拟滑动轨迹, 引入其轨迹模拟人手滑动

## macOS PlayCover / MaaTools（实验性支持）

### 中文说明

本实验性接入借鉴了 MAA（明日方舟小助手）的 [macOS PlayCover / MaaTools 接入思路](https://docs.maa.plus/zh-cn/manual/device/macos.html)，并使用 [OASX](https://github.com/runhey/OASX) 作为界面。我们已从 OASX Flutter 源码编译出一个可在 macOS 本地运行的 app，用于本集成验证；本 PR 不上传或分发该二进制。此功能仍处于试验性阶段，不代表官方 release 已经包含 macOS app。

Flutter app 仅是界面，不内置 Python 解释器、OCR、本地 OAS 服务或其依赖。请在 macOS 主机上安装 Python 3.10，创建 venv，并手动安装 [requirements-macos-playcover.txt](requirements-macos-playcover.txt) 中的 pip 包：

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-macos-playcover.txt
```

这份文件只是 pip 包清单，不包含 Python 解释器或 OCR 模型文件；这些内容也不会由 Flutter app 内置提供。

PlayCover 需要 MaaTools。请先按 [MAA macOS 手册](https://docs.maa.plus/zh-cn/manual/device/macos.html) 配置 PlayCover/MaaTools，然后在 OASX 现有下拉框中选择 PlayCover（`control=MacPlayTools`），`screenshot` 选择 `MacBGR`、`RGBA` 或 `MacSCK`，并将 `serial` 填为标题栏中的 `localhost:1718`。PlayCover、ADB 和 minitouch 是并列可选的控制方式；选择 `adb` 或 `minitouch` 时使用 Android 模拟器。

请在 PlayCover 中将游戏分辨率设置为 1280×720。OAS 要求使用该分辨率，否则无法正常识别和点击。

### English

This experimental integration follows the [macOS PlayCover / MaaTools approach used by MAA (MaaAssistantArknights)](https://docs.maa.plus/zh-cn/manual/device/macos.html) and uses [OASX](https://github.com/runhey/OASX) as its UI. We compiled an app from the OASX Flutter source that runs locally on macOS for integration validation; this PR does not upload or distribute that binary. This remains experimental support and does not claim that an official release already includes a macOS app.

The Flutter app is UI-only. It does not bundle a Python interpreter, OCR, the OAS service, or its dependencies. On the macOS host, install Python 3.10, create a venv, and manually install the pip packages in [requirements-macos-playcover.txt](requirements-macos-playcover.txt):

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-macos-playcover.txt
```

That file is only a pip package list; it does not include the Python interpreter or OCR model files, and the Flutter app does not bundle or provide them.

PlayCover requires MaaTools. First configure PlayCover/MaaTools according to the [MAA macOS manual](https://docs.maa.plus/zh-cn/manual/device/macos.html), then in OASX's existing dropdowns select PlayCover (`control=MacPlayTools`), choose `MacBGR`, `RGBA`, or `MacSCK` for `screenshot`, and set `serial` to `localhost:1718` shown in the title bar. PlayCover, ADB, and minitouch are parallel control options; selecting `adb` or `minitouch` uses the Android emulator.

Set the game resolution in PlayCover to 1280×720. OAS requires this resolution; otherwise recognition and tapping will not work correctly.

## 联系/加入我们 Contact/Join Us



相对于其他的游戏，阴阳师玩家总体而言对脚本这类工具具有极高的排斥性。树大招风，无论你是否喜欢 OAS ，我们都希望你不在互联网上进行宣传，这保护 OAS , 也保护开发者们。

为此保持较高的入群门槛: 
#### QQ交流群: 1群465946275 2群1076565458
- 你的QQ等级必须大于32级(🌞🌞)，注册时间超过一年，低等级账号成分复杂，还请见谅。
- 你必须拥有一个 Github 账户来点一个 **Star** (这并不影响你入群后取消Star)，同样的要求注册时间过半年。
- 入群验证填入你的 Github `username`(不是`name`)，无需在意问题是什么，由QQ机器人审核(机器永远的对的)。

#### QQ开发群: 207613181 (有意开发本项目请加此群, 请不要胡乱加群)

- 开发规划：[#354](https://github.com/runhey/OnmyojiAutoScript/issues/354)
- OAS 继承了 Alas 的设计思路，极大简便了开发，欢迎提交 PR，挑选你感兴趣的部分进行开发即可。
- OAS 仍在活跃中， 我们会不定期发布未来的工作在 Issues 上并标记为 `help wanted`，欢迎向 OAS 提交 PR，我们会认真阅读你的每一行代码的。

## 安装 Installation 

- [学会提问](https://runhey.github.io/OnmyojiAutoScript-website/docs/user-manual/scientific-question): 最基本的要求，**必看必学必会**
- [用户手册](https://runhey.github.io/OnmyojiAutoScript-website/docs/user-manual/getting-started): 在线手册，不定期更新，包含所有使用说明
- [安装教程](https://runhey.github.io/OnmyojiAutoScript-website/docs/user-manual/installation): 保姆式安装手册,多翻翻有惊喜
- [开发文档](https://runhey.github.io/OnmyojiAutoScript-website/docs/development/preamble): 虽然迭代很多、年久失修，但入门开发必读，具体以源码为准

## 鸣谢 Acknowledgements

感谢所有参与到开发/测试中的朋友们

[![Contributors](https://contributors-img.web.app/image?repo=runhey/OnmyojiAutoScript)](https://github.com/runhey/OnmyojiAutoScript/graphs/contributors)

感谢所有完善文档的朋友们

[![Contributors](https://contributors-img.web.app/image?repo=runhey/OnmyojiAutoScript-website)](https://github.com/runhey/OnmyojiAutoScript-website/graphs/contributors)

<div align="center">

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=runhey/OnmyojiAutoScript&type=Date)](https://star-history.com/#runhey/OnmyojiAutoScript&Date)


## ⚡ Visitor count

![](https://profile-counter.glitch.me/runhey-OnmyojiAutoScript/count.svg)

</div>
