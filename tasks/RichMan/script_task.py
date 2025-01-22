# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd


from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import RichMan
from tasks.RichMan.mall.mall import Mall
from tasks.RichMan.guild import Guild
from tasks.RichMan.shrine import Shrine
from tasks.RichMan.thousand_things import ThousandThings


class ScriptTask(Mall, Guild, ThousandThings, Shrine):

    def run(self):
        con: RichMan = self.config.rich_man
        # 千物宝箱
        self.execute_tt(con.thousand_things)
        # 神龛
        self.execute_shrine(con.shrine)
        # 功勋商店
        self.execute_guild(con.guild_store)
        # 商店
        self.execute_mall()

        self.set_next_run(task='RichMan', success=True, finish=False)

        raise TaskEnd('RichMan')













if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
    # t.execute_mall()



