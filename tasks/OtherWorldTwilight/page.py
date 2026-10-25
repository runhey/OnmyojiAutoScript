from tasks.GameUi.default_pages import page_demon_encounter
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.OtherWorldTwilight.assets import OtherWorldTwilightAssets

page_owt = Page(any_of(OtherWorldTwilightAssets.I_OWT_FIRE, OtherWorldTwilightAssets.I_OWT_TEAM))
page_owt.connect(page_demon_encounter, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_owt->page_demon_encounter")
page_demon_encounter.connect(page_owt, OtherWorldTwilightAssets.I_DE_TO_OTHER_WORLD,
                             key="page_demon_encounter->page_owt")
