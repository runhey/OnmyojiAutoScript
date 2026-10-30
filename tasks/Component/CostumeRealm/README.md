# 结界皮肤：月海游星

枚举：`RealmType.COSTUME_REALM_YUEHAI_YOUXING`；值：`costume_realm_yuehai_youxing`。

## 素材与边界
- 新增结界皮肤按钮/页面标志、结界卡收益宝箱、体力食盒、普通状态经验酒壶共 4 个模板。
- 原始完整截图为 1282×721，归一化为 1280×720 后裁取局部图标，不保存带账号信息的完整截图到代码目录。
- 三个旗子入口属于独立鲤鱼旗配置；保留现有覆盖逻辑，不能把鸢戏游鲤的图片硬编码成结界皮肤。
- 已离线验证截图中的鸢戏游鲤 3 个入口可用现有素材多尺度识别。
- 食盒“取出”与酒壶“提取”弹窗按用户确认继续用原素材。
- 未采集寄养领取 `I_UTILIZE_EXP` 和酒壶已满 `I_BOX_EXP_MAX`，保留原规则，不声称新状态已验证。
- 新皮肤的结界卡收益宝箱较默认位置向下移动；旧搜索范围会漏检，故需要替换对应 ROI。

## 应用
`CostumeBase.check_costume()` 先应用结界资源，再应用鲤鱼旗。原地更新共享 RuleImage，保留引用并清除图片、名称等缓存；切回默认时恢复原资源。

在 OASX 选择“自定义游戏装饰 → 结界皮肤 → 月海游星”；鲤鱼旗单独选择与游戏一致的选项。新增枚举需要重启后端；新增中文需要在 OASX 设置中执行“翻译更新”并重新打开 OASX。

## 生成资源及测试
在项目根目录执行：

```python
from dev_tools.assets_extract import AssetsExtractor
AssetsExtractor("tasks/Component/CostumeRealm").extract()
```

`realm_yuehai_youxing/image.json` 是资源元数据来源。不要手动修改自动生成的规则内容。

```powershell
.\toolkit\python.exe -m unittest discover -s tests/tasks/Component/CostumeRealm -v
```

仅做离线测试，没有操控实际游戏；其他鲤鱼旗、动画帧及缺失状态仍需后续验证。
