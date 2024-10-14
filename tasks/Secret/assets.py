from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

# This file was automatically generated by ./dev_tools/assets_extract.py.
# Don't modify it manually.
class SecretAssets: 


	# Click Rule Assets
	# description 
	C_SE_CLICK_LAYER = RuleClick(roi_front=(434,155,100,100), roi_back=(434,155,100,100), name="se_click_layer")


	# Image Rule Assets
	# 进入 
	I_SE_ENTER = RuleImage(roi_front=(1145,593,100,100), roi_back=(1145,593,100,100), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_enter.png")
	# 秘闻挑战 
	I_SE_FIRE = RuleImage(roi_front=(1108,551,100,100), roi_back=(1100,541,120,120), threshold=0.7, method="Template matching", file="./tasks/Secret/se/se_se_fire.png")
	# 排行 
	I_SE_PLACEMENT = RuleImage(roi_front=(1013,570,50,48), roi_back=(996,555,79,81), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_placement.png")
	# 勾玉 
	I_SE_JADE = RuleImage(roi_front=(305,208,28,33), roi_back=(305,208,28,33), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_jade.png")
	# 最后一个的勾玉 
	I_SE_JADE_LAST = RuleImage(roi_front=(302,565,37,40), roi_back=(302,565,37,40), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_jade_last.png")
	# 战斗赢 
	I_SE_BATTLE_WIN = RuleImage(roi_front=(436,62,100,100), roi_back=(436,62,100,100), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_battle_win.png")
	# 已经完成可以退出 
	I_SE_FINISHED_1 = RuleImage(roi_front=(441,546,40,43), roi_back=(441,546,40,43), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_se_finished_1.png")
	# 御魂溢出 
	I_OVER_GHOST = RuleImage(roi_front=(609,410,65,28), roi_back=(609,410,65,28), threshold=0.8, method="Template matching", file="./tasks/Secret/se/se_over_ghost.png")


	# Ocr Rule Assets
	# 未通关 
	O_SE_NO_PASS = RuleOcr(roi=(428,151,262,248), area=(428,151,262,248), mode="Full", method="Default", keyword="未通关", name="se_no_pass")
	# 第一个位置的层数 
	O_SE_LAYER_1 = RuleOcr(roi=(210,150,44,39), area=(210,150,44,39), mode="Single", method="Default", keyword="", name="se_layer_1")
	# Ocr-description 
	O_SE_LAYER_10 = RuleOcr(roi=(210,507,34,34), area=(210,507,34,34), mode="Single", method="Default", keyword="拾", name="se_layer_10")
	# Ocr-description 
	O_SE_LAYER_9 = RuleOcr(roi=(211,373,35,33), area=(211,373,35,33), mode="Single", method="Default", keyword="玖", name="se_layer_9")
	# Ocr-description 
	O_SE_LAYER_8 = RuleOcr(roi=(212,237,34,34), area=(212,237,34,34), mode="Single", method="Default", keyword="捌", name="se_layer_8")
	# 后面的时候识别为通关的 
	O_SE_NO_PASS_LAST = RuleOcr(roi=(429,381,180,234), area=(429,381,180,234), mode="Full", method="Default", keyword="未通关", name="se_no_pass_last")
	# 勾玉 
	O_SE_JADE = RuleOcr(roi=(327,230,23,24), area=(327,230,23,24), mode="Digit", method="Default", keyword="", name="se_jade")
	# 金币 
	O_SE_GOLD = RuleOcr(roi=(363,226,48,21), area=(363,226,48,21), mode="Digit", method="Default", keyword="", name="se_gold")


	# Swipe Rule Assets
	# 向下滑动 
	S_SE_DOWN_SEIPE = RuleSwipe(roi_front=(229,520,124,27), roi_back=(217,390,145,35), mode="default", name="se_down_seipe")


