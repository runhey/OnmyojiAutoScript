from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class WeeklyTriflesAssets: 


	# Click Rule Assets
	# 进入已经挑战的第一个 
	C_WT_AB_CLICK = RuleClick(roi_front=(168,362,68,72), roi_back=(168,362,68,72), name="wt_ab_click")


	# Image Rule Assets
	# 今日挑战 
	I_WT_DAY_BATTLE = RuleImage(roi_front=(40,365,65,66), roi_back=(40,365,65,66), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/area_boss/area_boss_wt_day_battle.png")
	# 今天一个都没有打 
	I_WT_NO_DAY = RuleImage(roi_front=(167,360,72,69), roi_back=(167,360,72,69), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/area_boss/area_boss_wt_no_day.png")
	# 地鬼分享 
	I_WT_SHARE_AB = RuleImage(roi_front=(1183,308,45,39), roi_back=(1136,292,105,79), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/area_boss/area_boss_wt_share_ab.png")
	# 分享勾玉 
	I_WT_AB_JADE = RuleImage(roi_front=(797,515,432,97), roi_back=(797,515,432,97), threshold=0.6, method="Template matching", file="./tasks/WeeklyTrifles/area_boss/area_boss_wt_ab_jade.png")
	# 微信分享 
	I_WT_AB_WECHAT = RuleImage(roi_front=(1032,643,50,56), roi_back=(1032,643,50,56), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/area_boss/area_boss_wt_ab_wechat.png")


	# Image Rule Assets
	# 进入普通召唤 
	I_BM_ENTER = RuleImage(roi_front=(435,601,62,68), roi_back=(435,601,62,68), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/broken_amulet/broken_amulet_bm_enter.png")
	# 确定 
	I_BM_CONFIRM = RuleImage(roi_front=(418,620,173,59), roi_back=(418,620,173,59), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/broken_amulet/broken_amulet_bm_confirm.png")
	# 再次召唤 
	I_BM_AGAIN = RuleImage(roi_front=(686,617,178,60), roi_back=(686,617,178,60), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/broken_amulet/broken_amulet_bm_again.png")


	# Ocr Rule Assets
	# 左上角的数量 
	O_BA_AMOUNT_1 = RuleOcr(roi=(568,15,79,29), area=(568,15,79,29), mode="Digit", method="Default", keyword="", name="ba_amount_1")
	# 召唤的时候的数量 
	O_BA_AMOUNT_2 = RuleOcr(roi=(762,570,118,35), area=(762,570,118,35), mode="DigitCounter", method="Default", keyword="", name="ba_amount_2")


	# Click Rule Assets
	# 微信分享的点击 
	C_WT_WECHAT = RuleClick(roi_front=(470,111,337,44), roi_back=(470,111,337,44), name="wt_wechat")


	# Image Rule Assets
	# 点击“式神” 
	I_WT_SHIKIAGMI = RuleImage(roi_front=(494,650,56,49), roi_back=(494,650,56,49), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_shikiagmi.png")
	# 点击式神绘卷 
	I_WT_SCROLL = RuleImage(roi_front=(1128,615,77,67), roi_back=(1128,615,77,67), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_scroll.png")
	# 点击分享 
	I_WT_COLLECT = RuleImage(roi_front=(1170,606,78,83), roi_back=(1170,606,78,83), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_collect.png")
	# 百鬼夜行图 
	I_WT_SCROLL_1 = RuleImage(roi_front=(1180,27,28,121), roi_back=(1159,12,65,152), threshold=0.7, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_scroll_1.png")
	# 百妖风物鉴 
	I_WT_SCROLL_2 = RuleImage(roi_front=(1182,24,24,122), roi_back=(1163,12,63,155), threshold=0.7, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_scroll_2.png")
	# 微信分享 
	I_WT_COLLECT_WECHAT = RuleImage(roi_front=(640,617,70,63), roi_back=(640,617,70,63), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_collect_wechat.png")
	# 二维码 
	I_WT_QR_CODE = RuleImage(roi_front=(473,161,336,96), roi_back=(404,112,483,168), threshold=0.65, method="Template matching", file="./tasks/WeeklyTrifles/collect/collect_wt_qr_code.png")


	# Image Rule Assets
	# 秘闻进入 
	I_WT_ENTER_SE = RuleImage(roi_front=(1145,598,100,100), roi_back=(1145,598,100,100), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/secret/secret_wt_enter_se.png")
	# 秘闻分享 
	I_WT_SE_SHARE = RuleImage(roi_front=(911,570,46,43), roi_back=(897,559,85,64), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/secret/secret_wt_se_share.png")
	# 微信 
	I_WT_SE_WECHAT = RuleImage(roi_front=(1023,630,56,57), roi_back=(1023,630,56,57), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/secret/secret_wt_se_wechat.png")
	# 勾玉 
	I_WT_SE_JADE = RuleImage(roi_front=(1129,529,35,39), roi_back=(1129,529,35,39), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/secret/secret_wt_se_jade.png")
	# 排行 
	I_WT_SE_RANK = RuleImage(roi_front=(1017,572,45,44), roi_back=(989,556,103,81), threshold=0.8, method="Template matching", file="./tasks/WeeklyTrifles/secret/secret_wt_se_rank.png")


