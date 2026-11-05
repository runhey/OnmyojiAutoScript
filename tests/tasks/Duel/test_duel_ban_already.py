# -*- coding: utf-8 -*-
"""
名仕禁选阶段按钮状态识别与点击节流。

背景: 名仕斗技双方各禁选一名式神。我方禁选完成后按钮会变成「已禁选」且不可点击,
继续点击会触发同键连点保护(GameTooManyClickError), 游戏据此判定卡死并重启。
"""
from pathlib import Path

import numpy as np
import pytest

from tasks.Duel import script_task as duel_script
from tasks.Duel.assets import DuelAssets

_REPO_ROOT = Path(__file__).resolve().parents[3]

# 记录模板原始 roi_front, 匹配会原地改写 roi_front, 每个用例前恢复
_BAN_ROI = tuple(DuelAssets.I_BAN.roi_front[:4])
_BAN_ALREADY_ROI = tuple(DuelAssets.I_BAN_ALREADY.roi_front[:4])


@pytest.fixture(autouse=True)
def _chdir_repo_root(monkeypatch):
    """模板是相对路径, 保证从仓库根目录加载模板图"""
    monkeypatch.chdir(_REPO_ROOT)


def _canvas():
    return np.full((720, 1280, 3), 235, dtype=np.uint8)


def _paste(canvas, rule, x, y):
    h, w = rule.image.shape[:2]
    canvas[y:y + h, x:x + w] = rule.image
    return canvas


def _match(rule, image, roi_front):
    rule.roi_front = list(roi_front)
    return rule.match(image)


def test_clickable_ban_button_is_not_marked_as_already_banned():
    """可点击状态: 能匹配到「禁选」, 不能匹配到「已禁选」"""
    image = _paste(_canvas(), DuelAssets.I_BAN, _BAN_ROI[0], _BAN_ROI[1])
    assert _match(DuelAssets.I_BAN, image, _BAN_ROI) is True
    assert _match(DuelAssets.I_BAN_ALREADY, image, _BAN_ALREADY_ROI) is False


def test_already_banned_button_is_detected():
    """已禁选: 「禁选」整体右移并被「已」印章覆盖, 两条规则都应命中"""
    image = _canvas()
    _paste(image, DuelAssets.I_BAN, 1158, 565)  # 已禁选时「禁选」右移约 19px
    _paste(image, DuelAssets.I_BAN_ALREADY, _BAN_ALREADY_ROI[0], _BAN_ALREADY_ROI[1])
    assert _match(DuelAssets.I_BAN, image, _BAN_ROI) is True
    assert _match(DuelAssets.I_BAN_ALREADY, image, _BAN_ALREADY_ROI) is True


def test_already_banned_rule_does_not_match_plain_ban_button():
    """只有「禁选」时不能误判成已禁选, 否则整场斗技都不会点禁选"""
    image = _paste(_canvas(), DuelAssets.I_BAN, _BAN_ROI[0], _BAN_ROI[1])
    assert _match(DuelAssets.I_BAN_ALREADY, image, _BAN_ALREADY_ROI) is False


class FakeDuel:
    I_BAN = DuelAssets.I_BAN
    I_BAN_ALREADY = DuelAssets.I_BAN_ALREADY

    def __init__(self, ban_visible=True, already_banned=False):
        self.ban_visible = ban_visible
        self.already_banned = already_banned
        self.ban_clicks = 0
        self.is_celeb = False

    def appear(self, target, interval=None, threshold=None):
        if target is DuelAssets.I_BAN:
            return self.ban_visible
        if target is DuelAssets.I_BAN_ALREADY:
            return self.already_banned
        raise AssertionError(f'unexpected target: {target}')

    def appear_then_click(self, target, action=None, interval=None, threshold=None, duration=None):
        assert target is DuelAssets.I_BAN
        self.ban_clicks += 1
        return True


def test_ban_is_clicked_once_when_button_available():
    fake = FakeDuel(ban_visible=True, already_banned=False)
    in_ban_page, count = duel_script.ScriptTask._ban_shikigami_once(fake, 0)
    assert in_ban_page is True
    assert fake.ban_clicks == 1
    assert count == 1
    assert fake.is_celeb is True


def test_ban_is_not_clicked_again_when_already_banned():
    """核心回归: 按钮已变成「已禁选」后必须停止点击, 否则触发同键连点保护"""
    fake = FakeDuel(ban_visible=True, already_banned=True)
    in_ban_page, count = duel_script.ScriptTask._ban_shikigami_once(fake, 1)
    assert in_ban_page is True
    assert fake.ban_clicks == 0
    assert count == 1


def test_ban_click_is_capped_when_already_state_missed(monkeypatch):
    """兜底: 「已禁选」识别失败时, 点击次数也不能堆到连点保护阈值"""
    monkeypatch.setattr(duel_script, 'sleep', lambda seconds: None)
    fake = FakeDuel(ban_visible=True, already_banned=False)
    in_ban_page, count = duel_script.ScriptTask._ban_shikigami_once(fake, 5)
    assert in_ban_page is True
    assert fake.ban_clicks == 0
    assert count == 5


def test_not_in_ban_page_keeps_counter_untouched():
    fake = FakeDuel(ban_visible=False, already_banned=False)
    in_ban_page, count = duel_script.ScriptTask._ban_shikigami_once(fake, 2)
    assert in_ban_page is False
    assert fake.ban_clicks == 0
    assert count == 2
