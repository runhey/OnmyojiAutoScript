# 庭院菜单主题

新语明霄：`ThemeType.COSTUME_THEME_1`。配置默认仍为伊始之卷。

`theme1/image.json` 为生成源；图片为 1280×720 坐标系下的局部模板。仅生成本组件：

```python
from dev_tools.assets_extract import AssetsExtractor
AssetsExtractor("tasks/Component/CostumeTheme").extract()
```

在项目根目录用内置 Python 执行。不要手改自动生成的 assets.py。

`theme.py` 原地更新 GameUiAssets 的共享 RuleImage，而非替换引用，确保已构建的导航边同步生效；切换时重置图片、名称和特征缓存。支持从新主题切回默认。

覆盖卷轴和当前默认导航使用的 9 个入口；不新增纳物库导航，不自动更换游戏主题。截图素材经过 1282×721 至 1280×720 归一化，需在真实客户端进一步验证动态背景和通知角标。

离线回归测试（项目根目录）：

```powershell
.\toolkit\python.exe -m unittest discover -s tests/tasks/Component/CostumeTheme -v
```
