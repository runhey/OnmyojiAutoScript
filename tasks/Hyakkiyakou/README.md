


- agent: 砸豆子的决策模型
- slave: 针对百鬼对接模拟器的接口
- debugger.py: 辅助
---

detector: 检测器

tracker: 跟踪器

xxz7528的修改：
1.添加了根据稀有度选择鬼王的函数 in script_task
    -然而不太管用 因为识别率比较低 但也比没有好 偶尔能识别出来特征鲜明的ssr/sp
2.延长了完成百鬼后截图记录等待时间，避免截到一半的图 in script_task
3.添加了没有概率up时不砸ssr/sp的逻辑 in focus.py
4.添加了冰冻逻辑：仅当目标是ssr/sp且带概率up的时候允许砸冰冻buff，冰冻buff时只砸有概率up的ssr/sp和buff, 删除了gamma和script的冰冻判定逻辑
    -然而目前由于识别率比较低而且会把各种式神识别成sp蝉冰雪女 这套逻辑仅是添加了 没有启用（在script_task.py里还是会决策冰冻什么都不做）



