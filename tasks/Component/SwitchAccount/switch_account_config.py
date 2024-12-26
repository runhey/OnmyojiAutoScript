from pydantic import Field, BaseModel

from tasks.Component.config_base import DateTime


class AccountInfo(BaseModel):
    """
        character:   角色名字
        svr:         角色所在服务器
        account:     账号
        appleOrAndroid:  角色所属平台 安卓/苹果(可选)
                False           Apple
                True            Android
    """
    character: str = Field(default="", description='character_help')
    svr: str = Field(default="", description="svr_help")
    account: str = Field(default="", description="account_help")
    # 为防止ocr出错 暂定格式 字符串以#分割
    account_alias: str = Field(default="", description="account_alias_help")
    apple_or_android: bool = Field(default=True, description="apple_or_android_help")
    # 上一次执行成功的时间 ,防止出错时重复登录浪费时间
    last_complete_time: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description="last_complete_time_help")

    def is_account_alias(self, ocr_account):
        tmp_account = AccountInfo.preprocessAccount(self.account)
        if ocr_account == self.account or ocr_account.startswith(tmp_account):
            return True
        if not self.account_alias:
            return False
        _accountAliasList = self.account_alias.split('#')
        for alias in _accountAliasList:
            if ocr_account.startswith(alias):
                return True
        return False

    @staticmethod
    def preprocessAccount(account: str):
        """
            预处理账号信息 便于比对
            邮箱账号        去除@后面的部分 防止@被识别为其他
        @param account:
        @type account:
        @return:
        @rtype:
        """
        return account.split('@')[0]

    def is_valid(self):
        return self.character!="" and self.character is not None