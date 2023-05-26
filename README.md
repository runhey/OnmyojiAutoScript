欢迎大家捧场

![image-20230526205041711](https://runhey-img-stg1.oss-cn-chengdu.aliyuncs.com/img2/202305262050939.png)

## 设计思路（其实大部分就是alas的设计）

<details>
<summary></summary>

- 核心

  - 看上图左侧的＋号，每一个被称为script实例，可以简单的理解为不同的模拟器配置或者是不同的任务配置，每个实例由一个config.json文件来驱动。config来管理任务的调度，配置任务的不同的参数。
  - 这个脚本的目的是实现全程的7x24的接管游戏，去享受生活而不是在阴阳师这里上班，所以我也是有空更新。
  - 对于每个任务的执行过程就是比较常规的截图（识别）+控制（点击啥的），在这里会选择和我[早期的设计](https://github.com/runhey/Uowl)一致，设计一个原子化的模块化的配置信息。比如说要识别某个图片会添加一份json数据来设置识图的范围、方式、识别的图片。点击的话也会有一份json数据配置点击的随机概率、范围等等。每一个操作都一份可格式化的配置信息，而不是同alas一样将识别图片和点击一起抽象成一个button。
  - 噢对了我在写代码的时候命名上并没有针对oas，因此说你可以fork该项目使用到你的游戏脚本上

- 部署方式：用的是batchfile + python(env+pip) + git 

  - 具体的说就是，需要先下载一个安装包里面包含一个最小python和git环境，运行后下拉仓库，完事后安装依赖，再完事后启动gui。


#### 设计架构


- gui部分

  - 用的是这个库[FluentUI for QML ](https://github.com/zhuzichu520/FluentUI).是用的qml来写，我想懂这个语言的人不多吧，跟python通信一个是靠注入上下文，另一个是靠zerorpc。

- 程序入口

  - 有两个根目录下的gui.py和script.py。而gui.py会根据配置文件config.json来实例化不同的script，script就是某个具体的脚本过程。

- 进程

  - gui启动自带一个进程，每有一个script就会继续多一个进程，单独建一个进程来提供ocr服务。一般用zerorpc来进程通信。

- 运行过程

  - gui 按钮点击后就会开始从script上启动服务。script持有一个设备device，一个配置config，一个任务task。这个时候调度器（其实就是config）会更新出running、pending and waiting tasks。选择runing的去执行，任务的执行过程就是一个大的状态机。

#### 模块设计

- config模块，主要是有一个类Config，主要是对配置的文件的接口，以及一些代码中手工配置的参数。（我还没写好从yaml到template.json和从template更新配置）
- device模块，四个方向的功能管理模拟器，管理游戏，截图和控制

</details>    
