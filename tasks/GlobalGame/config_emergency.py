# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, time
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

class FriendInvitation(str, Enum):
    '''
    协作
    '''
    ACCEPT = 'accept'
    REJECT = 'reject'
    ONLY_JADE = 'only_jade'  # 仅接受勾玉邀请
    JADE_AND_FOOD = 'jade_and_food' # 勾协+粮协
    IGNORE = 'ignore'

class WhenNetworkAbnormal(str, Enum):
    RESTART = 'restart'
    WAIT_10S = 'wait_10s'

class WhenNetworkError(str, Enum):
    RESTART = 'restart'

# 也可以是左边的邀请什么的
class Emergency(BaseModel):
    friend_invitation: FriendInvitation = Field(default=FriendInvitation.ACCEPT,description='friend_invitation_help')
    # invitation_detect_interval: int = Field(default=5, description='invitation_detect_interval_help')
    when_network_abnormal: WhenNetworkAbnormal = Field(default=WhenNetworkAbnormal.WAIT_10S, description='when_network_abnormal_help')
    when_network_error: WhenNetworkError = Field(default=WhenNetworkError.RESTART, description='when_network_error_help')
    home_client_clear: bool = Field(default=True, description='home_client_clear_help')


