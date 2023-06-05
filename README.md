![image-20230526205041711](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img2/202305262050939.png)

## 设计思路（其实大部分就是alas的设计）

<details>
<summary></summary>

### 核心

- 多实例化：简单理解为不同的模拟器配置或者是不同的任务配置，每个实例由一个config.json文件来驱动。Config来管理任务的调度，配置任务的不同的参数。
- 全程接管：阴阳师已经走过了颠覆时期，三次元痒痒鼠玩家本应游戏中畅行无阻，而游戏世界7x24永续航。
- 游戏通用：我们在参考Alas时发现其同碧蓝航线有很强的耦合性，于此设计该项目将减少同阴阳师的耦合，因此你可以fork该项目使用到你的游戏脚本上
- 操作格式化：对于每个任务的执行过程就是比较常规的截图+控制，我们选择同[早期的设计](https://github.com/runhey/Uowl)一致，设计一个原子化的模块化的配置信息。比如说要识别某个图片会添加一份json数据来设置识图的范围、方式、识别的图片。点击的话也会有一份json数据配置点击的随机概率、范围等等。每一个操作都一份可格式化的配置信息，而不是同alas一样将识别图片和点击一起抽象成一个button。



### 设计架构

- 部署方式：batchfile + python(env+pip) + git 。具体的说就是，需要先下载一个安装包里面包含一个最小python和git环境，运行后下拉仓库，完事后安装依赖，再完事后启动gui。

- GUI实现:  用的是这个库[FluentUI for QML ](https://github.com/zhuzichu520/FluentUI).是用的qml来写，我想懂这个语言的人不多吧，跟python通信一个是靠注入上下文，另一个是靠zerorpc。

- 程序入口:  有两个根目录下的gui.py和script.py。而gui.py会根据配置文件config.json来实例化不同的script，script就是某个具体的脚本过程。

- 脚本进程:  gui启动自带一个进程，每有一个script就会继续多一个进程，单独建一个进程来提供ocr服务。一般用zerorpc来进程通信。

- 运行过程:  gui 按钮点击后就会开始从script上启动服务。script持有一个设备device，一个配置config，一个任务task。这个时候调度器（其实就是config）会更新出running、pending and waiting tasks。选择runing的去执行，任务的执行过程就是一个大的状态机。


### 模块设计


</details>    



## SETUP

oas目前还在开发中，我们期待你的加入，Q群: 465946275

### 浅尝即可

如果单纯了解本项目，你可以下载[最新发布](https://github.com/runhey/OnmyojiAutoScript/releases)，会自动安装环境。

具体为：下载->解压->打开`oas.exe`， 稍等一两分钟待环境安装好后即可启动

### 参与开发

1. 打开本项目[主仓库](https://github.com/runhey/OnmyojiAutoScript/tree/master), 点击右上角的 `Fork`，然后点击下面绿色的 `Create fork`

2. 进入自己账号下的 oas仓库，并 `clone` 其中的 `dev` 分支到本地
	```
	git clone url -b dev
	```

3. 下载[最新环境包](https://github.com/runhey/OnmyojiAutoScript/releases), 解压复制`toolkit`，`deploy`两个文件夹和`console.bat`到本地的仓库根目录，`toolkit`里面包含python最小环境、git环境和GUI启动环境。

3. 安装pip库, 安装后你可以执行`gui.py`启动进行测试

   ```
   ./toolkit/python.exe -m pip install -r requirements.txt 
   ```
   
5. 此时你可以进行开发了，建议完成所有功能/任务后，再提交 `commit`, 别忘了按照下面的 `统一格式` 写上 `message`

   ```
   git commit -m 'message'
   ```
   >`message`的统一格式
   >```
   >doc(your part): your changes
   >feat(module name): your add
   >fix(module name): your fix
   >```

6. 完成开发后，推送本地分支到自己的仓库

   ```
   git push -u origin
   ```

   > 第一次 `push` 代码需要按照提示设置上传流(`--set-upstream`)

5. 打开 [主仓库](https://github.com/runhey/OnmyojiAutoScript/tree/master)。提交一个 `pull request` (会自动携带你 `commit` 的信息)，等待管理员通过。注意：要提交到 `dev` 分支上，别提交到 `master` 分支去了

### 开发IDE

- Pycharm
- QtCreator:  用于qml开发
- Linguist: Qt家的翻译器

## NEXT

| 进度表                                                       |
| :----------------------------------------------------------- |
| ✔自动化部署                                                  |
| ✔GUI引入工程                                                 |
| ✔config读写参数字段                                          |
| ✔优化window截图+控制                                         |
| ✔投屏到OAS                                                   |
| 🔨操作格式化json生成工具：可以从用户界面简单操作生成维护数据（包括✔图片匹配，点击操作，长按操作，滑动操作，ocr识别等等） |
| 📆Atom: 对于上一条数据的接口                                  |
| 📆实现ocr单独进程                                             |
| 📆到此我们可以（读参数）、（对游戏截屏控制）、（操控数据）。实现第一个脚本任务如挖土 |
| 📆重写device(从alas复制过来需要解耦)                          |
|                                                              |

| **更多**        | 难题             |
| --------------- | ---------------- |
| 📆实现更多的任务 | 如何输出Log到GUI |
| 📆建立任务调度   | 优化速度         |
|                 |                  |
