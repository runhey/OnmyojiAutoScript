# CostumeShikigami 幕间（式神录）皮肤支持

本目录用于为“幕间（式神录）”添加皮肤切换支持，方式与 `Costume` / `CostumeRealm` / `CostumeBattle` 一致：

- 每个皮肤一个子目录（例如 `sk1/`、`sk2/` ...）
- 在皮肤目录中用 GUI 采集模板，生成 `image.json`
- 使用 `./dev_tools/assets_extract.py` 自动生成 `assets.py`（无需手工修改）
- 在 `tasks/Component/Costume/costume_base.py` 的 `shikigami_costume_model` 中维护“原始资产名 -> 皮肤资产名”的映射

## 需要采集的关键元素（建议从高影响点开始）

- 进出式神录（GameUi）
  - `I_CHECK_RECORDS`（判定在式神录）
  - `I_MAIN_GOTO_SHIKIGAMI_RECORDS`（主页进入式神录的入口）
  - `I_RECORDS_CLOSE`（如皮肤影响关闭按钮）
- 御魂切换（SwitchSoul）
  - `I_SOU_CHECK_IN`（判定在预设面板/式神录）
  - `I_SOUL_PRESET`、`I_SOU_TEAM_PRESENT`（预设标题/标志）
  - `I_SOU_SWITCH_1` ~ `I_SOU_SWITCH_4`、`I_SOU_SWITCH_SURE`（切换/确认按钮）
  - `I_SOU_CHECK_GROUP_1` ~ `I_SOU_CHECK_GROUP_7`（分组选中标志）
  - `I_SOU_CLICK_PRESENT`（需要切换的预设按钮-深色）
  - `I_RECORD_SOUL_BACK`（返回）
- 御魂整理（SoulsTidy）
  - `I_ST_SOULS`、`I_ST_REPLACE`、`I_ST_TIDY`、`I_ST_GREED`（主要入口按钮）
  - `I_ST_GREED_HABIT`、`I_ST_FEED_NOW`、`I_ST_UNSELECTED`、`I_ST_GREED_CLOSE`、`I_ST_CAT`
  - `I_ST_DONATE`、`I_ST_GOD_PRESENT`、`I_ST_ABANDONED_SELECTED`、`I_ST_LEVEL_0`、`I_ST_GOLD`

> 提示：名称需与原始资产名一一对应，皮肤版命名约定为在末尾追加 `_1`、`_2` 等（例如：`I_ST_SOULS_1`）。

## 目录结构示例

```
CostumeShikigami/
  assets.py        # 由脚本自动生成（本骨架内提供了空类以便导入）
  README.md        # 本说明
  sk1/
    image.json    # GUI 采集得到
    sk1_st_souls.png
    sk1_sou_check_in.png
    ...
```

## 生成 assets.py

```bash
python ./dev_tools/assets_extract.py
```

脚本会读取各皮肤目录下的 `image.json`，自动在本目录生成/更新 `assets.py`，并提供 `CostumeShikigamiAssets` 类与各 RuleImage/RuleClick/... 的定义。

## 在 CostumeBase 中配置映射

`tasks/Component/Costume/costume_base.py` 中维护 `shikigami_costume_model`，使用动态生成方式减少重复代码：

```python
# 幕间（式神录）皮肤映射：ShikigamiType -> { 原始资产名: 皮肤资产名 }
_shikigami_base_assets = [
    # GameUi 进出式神录
    'I_CHECK_RECORDS',
    'I_RECORD_SOUL_BACK',
    # SwitchSoul 相关
    'I_SOUL_PRESET',
    'I_SOU_CHECK_IN',
    'I_SOU_TEAM_PRESENT',
    'I_SOU_CLICK_PRESENT',
    'I_SOU_SWITCH_SURE',
    # SwitchSoul 分组相关 (1-7组)
    *[f'I_SOU_CHECK_GROUP_{i}' for i in range(1, 8)],
    # SwitchSoul 队伍相关 (1-4队)
    *[f'I_SOU_SWITCH_{i}' for i in range(1, 5)],
    # SoulsTidy 相关
    'I_ST_SOULS',
    'I_ST_REPLACE',
]

shikigami_costume_model = {
    getattr(ShikigamiType, f"COSTUME_SHIKIGAMI_{i}"): {
        asset: f"{asset}_{i}" for asset in _shikigami_base_assets
    }
    for i in range(1, 21)  # 支持20种幕间皮肤
    if hasattr(ShikigamiType, f"COSTUME_SHIKIGAMI_{i}")  # 确保类型存在
}
```

当用户将配置 `costume_shikigami_type` 选择为 `COSTUME_SHIKIGAMI_1` 时，程序会在运行期将原始资产替换为对应皮肤资产（仅替换图片/阈值/ROI，不改点击坐标/OCR 规则）。

## 调试与测试
- 修改配置 `GlobalGame.costume_config.costume_shikigami_type` 为目标皮肤后运行脚本
- 逐步验证：主页进入式神录 -> 御魂切换的预设面板 -> 御魂整理入口和主要流程
- 如个别识别不稳，调整采集的 ROI 或阈值；必要时在 `replace_img(..., rp_roi_back=False)` 保留原 back ROI

