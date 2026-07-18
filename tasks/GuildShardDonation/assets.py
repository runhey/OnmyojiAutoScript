import cv2

from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr


class ScaledRuleOcr(RuleOcr):
    """稍微放大昵称区域，避免相邻的窄英文字母被 OCR 合并。"""

    scale = 1.25

    def pre_process(self, image):
        return cv2.resize(image, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_CUBIC)


class GuildShardDonationAssets:
    I_PRAYER_ENTRY = RuleImage(roi_front=(963, 628, 66, 71), roi_back=(920, 590, 145, 125), threshold=0.8, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_prayer_entry.png")
    I_PRAYER_PAGE = RuleImage(roi_front=(1166, 239, 61, 99), roi_back=(1140, 205, 105, 155), threshold=0.8, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_prayer_page.png")
    I_RECEIVED_POPUP = RuleImage(roi_front=(530, 178, 127, 25), roi_back=(470, 145, 260, 95), threshold=0.78, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_received_popup.png")
    I_GIVE = RuleImage(roi_front=(828, 274, 134, 66), roi_back=(800, 130, 330, 350), threshold=0.82, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_give.png")
    I_CONFIRM_DIALOG = RuleImage(roi_front=(432, 400, 416, 69), roi_back=(390, 370, 500, 125), threshold=0.78, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_confirm_dialog.png")
    I_CANCEL = RuleImage(roi_front=(432, 401, 180, 67), roi_back=(400, 380, 240, 110), threshold=0.8, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_cancel.png")
    I_CONFIRM = RuleImage(roi_front=(669, 401, 179, 66), roi_back=(640, 380, 240, 110), threshold=0.8, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_confirm.png")
    I_REWARD = RuleImage(roi_front=(357, 187, 566, 89), roi_back=(300, 140, 680, 170), threshold=0.75, method="Template matching", file="./tasks/GuildShardDonation/res/guild_shard_donation_reward.png")

    O_PLAYER_NAMES = ScaledRuleOcr(roi=(250, 135, 210, 345), area=(250, 135, 210, 345), mode="Full", method="Default", keyword="", name="player_names")
    O_CONFIRM_MESSAGE = RuleOcr(roi=(425, 285, 435, 75), area=(425, 285, 435, 75), mode="Full", method="Default", keyword="", name="confirm_message")

    C_RECEIVED_POPUP_CLOSE = RuleClick(roi_front=(838, 129, 58, 55), roi_back=(838, 129, 58, 55), name="received_popup_close")
    C_REWARD_CLOSE = RuleClick(roi_front=(500, 300, 280, 150), roi_back=(500, 300, 280, 150), name="reward_close")

    S_PRAYER_LIST_UP = RuleSwipe(roi_front=(650, 440, 50, 30), roi_back=(650, 190, 50, 30), mode="default", name="prayer_list_up")
