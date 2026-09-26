from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.base.timer import Timer
from module.logger import logger

from tasks.base_task import BaseTask


class LootStatistics(BaseTask):

    def loot_detect(self, image) -> dict:
        """

        :param image:
        :return: 返回举例
        {
        "RealmRaidPass": 1,
        }
        """
        return {}


