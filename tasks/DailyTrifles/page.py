from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import Page, page_mall

# 商店礼包屋页面
page_store_gift_room = Page(DailyTriflesAssets.I_GIFT_RECOMMEND)
page_store_gift_room.link(button=GameUiAssets.I_BACK_Y, destination=page_mall)
page_mall.link(button=DailyTriflesAssets.I_ROOM_GIFT, destination=page_store_gift_room)
