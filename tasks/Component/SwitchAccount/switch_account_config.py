from datetime import datetime
from pydantic import Field, BaseModel


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
    accountAlias: str = Field(default="", description="")
    appleOrAndroid: bool = Field(default=True, description="apple_or_android_help")
    # 上一次执行成功的时间 ,防止出错时重复登录浪费时间
    last_complete_time: datetime = Field(default=datetime(1970, 1, 1, 1, 1, 1), description="last_complete_time_help")

    def is_account_alias(self, ocr_account):
        tmp_account = AccountInfo.preprocessAccount(self.account)
        if ocr_account == self.account or ocr_account.startswith(tmp_account):
            return True
        if not self.accountAlias:
            return False
        _accountAliasList = self.accountAlias.split('#')
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
