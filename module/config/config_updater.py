# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from copy import deepcopy

from cached_property import cached_property

from deploy.utils import DEPLOY_TEMPLATE, poor_yaml_read, poor_yaml_write
from module.base.timer import timer
from module.config.utils import *

class ConfigUpdater:

    @timer
    def update_template(self, template_name: str = "template") -> None:
        """
        更新模板 。从args.json更新
        :param template_name:
        :return:
        """
        pass

    @timer
    def update_config(self, config_name: str ) -> None:
        """
        更新配置文件.从template更新
        :param config_name:
        :return:
        """
        pass