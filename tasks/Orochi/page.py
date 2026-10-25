from tasks.GameUi.default_pages import page_exploration, page_soul_zones, page_shikigami_records
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.Orochi.assets import OrochiAssets

# 御魂页面(魂1-魂10,魂11,12,13检查标志...)
page_orochi = Page(any_of(OrochiAssets.I_OROCHI_CHECK_10, OrochiAssets.I_OROCHI_CHECK_11,
                          OrochiAssets.I_OROCHI_CHECK_12, OrochiAssets.I_OROCHI_CHECK_13))
page_orochi.connect(page_exploration, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_orochi->page_exploration")
page_soul_zones.connect(page_orochi, OrochiAssets.I_OROCHI, key="page_soul_zones->page_orochi")

page_orochi.connect(page_shikigami_records, OrochiAssets.I_SHI_RECORDS,
                    key="page_orochi->page_shikigami_records", cost=2)
page_shikigami_records.connect(page_orochi, GlobalGameAssets.I_UI_BACK_YELLOW,
                               key="page_shikigami_records->page_orochi", cost=2)
