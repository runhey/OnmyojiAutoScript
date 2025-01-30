# This Python file uses the following encoding: utf-8
# @author ohspecial
# github https://github.com/ohspecial
from datetime import datetime ,timedelta
from enum import Enum

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_guild, page_main
from tasks.GuildBanquet.assets import GuildBanquetAssets

WEEKDAYDICT = {
    0: '星期一',
    1: '星期二',
    2: '星期三',
    3: '星期四',
    4: '星期五',
    5: '星期六',
    6: '星期日'
}

class Weekday(str,Enum):
    Monday: str = "星期一"
    Tuesday: str = "星期二" 
    Wednesday: str = "星期三"
    Thursday: str = "星期四"
    Friday: str = "星期五"
    Saturday: str = "星期六"
    Sunday: str = "星期日"
    
class ScriptTask(GameUi, GuildBanquetAssets):

    def run(self):
        self.run_time = self.config.guild_banquet.guild_banquet_time
        # 第一天宴会日期及时间
        self.banquet_day_1 = self.get_key_from_value(WEEKDAYDICT, self.run_time.day_1.value)
        self.banquet_day_1_start_time = self.run_time.run_time_1
        
        # 第二天宴会日期及时间
        self.banquet_day_2 = self.get_key_from_value(WEEKDAYDICT, self.run_time.day_2.value)
        self.banquet_day_2_start_time = self.run_time.run_time_2
        if not self.check_runtime():
            # 如果不是宴会日则设置下次运行时间
            self.plan_next_run()
            raise TaskEnd
        
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        
        if self.appear(self.I_FLAG):
            wait_count = 0
            wait_timer = Timer(270)
            wait_timer.start()
            logger.info("Start guild banquet!")
            self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            # 如果没有找到FLAG，可能是宴会时间没开始，5分钟后尝试再次查找
            time_now = datetime.now()
            time_later = time_now + timedelta(minutes=5)
            self.set_next_run(task='GuildBanquet',
                              finish=True,
                              target=time_later)
            raise TaskEnd
        # 开始宴会
        while True:
            self.screenshot()
            # 如果发现集结则表示在宴会中，没有则宴会结束
            if self.appear(self.I_FLAG, interval=10):
                logger.info("Wait in place or answer the question manually")
            else:
                logger.info("Guild banquet end")
                self.set_config()
                break
            if wait_timer.reached():
                wait_timer.reset()
                if wait_count >= 2:
                    # 记三次，时间到了就结束
                    logger.info('Guild banquet timeout')
                    break
                wait_count += 1
                logger.warning('In Guild banquet, wait')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.plan_next_run()
        raise TaskEnd
    
    def check_runtime(self) -> bool:
        """
        检查日期和时间, 是否是宴会日
        """
        now = datetime.now()
        day_of_week = now.weekday()
        # 判断当前日期是否是寮宴会日
        if day_of_week in [self.banquet_day_1, self.banquet_day_2]:
            return True
        
        # 如果当日时间超过22点，说明配置时间可能出错，设置下次失败运行时间
        if datetime.now().hour < 22:
            self.set_next_run(task="GuildBanquet", success=False)
            logger.error("Guild banquet time config error, set next run fail")
            return False

    def plan_next_run(self):
        # 安排次日宴会，便于复用
        today = datetime.now().weekday()
        
        if today < self.banquet_day_1:
            logger.info(f"Plan next run: {self.banquet_day_1_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=self.banquet_day_1 - today) 
        elif self.banquet_day_1 <= today < self.banquet_day_2:
            logger.info(f"Plan next run: {self.banquet_day_2_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_2_start_time, time_delta=self.banquet_day_2 - today)
        elif self.banquet_day_2 <= today:
            logger.info(f"Plan next run: {self.banquet_day_1_start_time}")
            self.custom_next_run(task='GuildBanquet', custom_time=self.banquet_day_1_start_time, time_delta=7 - today + self.banquet_day_1) 
    
    def get_key_from_value(self, dict, value):
        return [k for k, v in dict.items() if v == value][0]
    
    def get_weekday_enum(self, value: str) -> Weekday:
        for day in Weekday:
            if day.value == value:
                return day
        
    def set_config(self):
        """
        修改周几配置时会出现警告
        UserWarning: Pydantic serializer warnings:
  Expected `enum` but got `Weekday` with value `<Weekday.Thursday: '星期四'>` - serialized value may not be as expected
        """
        try:
            # 当结束宴会时，设置宴会时间的日期及时间，宴会时间设置为运行结束时间提前15分钟
            next_time = datetime.now() - timedelta(minutes=15)
            today = datetime.now().weekday()          
            # 修改配置文件
            if today == self.banquet_day_1:
                self.run_time.run_time_1 = next_time
            elif today == self.banquet_day_2:
                self.run_time.run_time_1 = next_time
            elif today < self.banquet_day_1:
                self.run_time.day_1 = self.get_weekday_enum(WEEKDAYDICT.get(today))
                self.run_time.run_time_1 = next_time
            elif today > self.banquet_day_2:
                self.run_time.day_2 = self.get_weekday_enum(WEEKDAYDICT.get(today))    
                self.run_time.run_time_2 = next_time
            else:
                # 如果当前时间在两个配置时间之间，则默认把工作日设置第一天，周末设为第二天
                if today <= 4:  # 工作日
                    self.run_time.day_1 = self.get_weekday_enum(WEEKDAYDICT.get(today))
                    self.run_time.run_time_1 = next_time
                else:  # 周末
                    self.run_time.day_2 = self.get_weekday_enum(WEEKDAYDICT.get(today))       
                    self.run_time.run_time_2 = next_time
            logger.info(f"Set next run time: {self.run_time}")
            
            self.config.save()
        except Exception as e:
            logger.error(f"Error setting banquet config: {e}")
            raise TaskEnd


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('xiaohao')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()

