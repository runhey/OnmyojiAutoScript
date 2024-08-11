# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from abc import abstractmethod

class BaseActivity(GeneralBattle):
    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面
        :return:
        """
        pass

    @abstractmethod
    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """