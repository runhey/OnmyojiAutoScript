from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList

class GuildActivityMonitorAssets:
	# 寮活动通知区域OCR识别
	# ROI: x=13, y=213, width=457, height=86
	O_GUILD_ACTIVITY_NOTIFY = RuleOcr(roi=(13,213,457,86), area=(13,213,457,86), mode="Full", method="Default", keyword="", name="guild_activity_notify")

