"""Persistent, configurable account handoff, independent of native UI code."""

import json
import math
import os
import re
import tempfile
from pathlib import Path
from time import time


class AccountYield(BaseException):
    """Unwind task protection handlers without treating a handoff as failure."""


def other_device_dialog(rows):
    """Require a confident central message and an associated dialog control."""
    texts = []
    button = False
    for text, score, box in rows:
        x1, y1, x2, y2 = box
        if score < .9 or not (250 <= x1 < x2 <= 1030 and 160 <= y1 < y2 <= 570):
            continue
        normalized = re.sub(r"\s|[，。！!？?：:]", "", text)
        texts.append(normalized)
        if y1 >= 320 and normalized in {"确定", "确认", "重新登录", "返回登录", "重新连接", "知道了"}:
            button = True
    message = "".join(texts)
    pattern = r"(?:账号|帐号|账户).{0,16}(?:其他|其它|另一|别的).{0,8}(?:设备|地方|客户端|终端).{0,12}(?:登录|登陆)"
    return bool(button and re.search(pattern, message))


class Handoff:
    def __init__(self, path, clock=time, pause_minutes=20):
        self.path = Path(path)
        self.clock = clock
        self._pause_minutes = pause_minutes

    def configured_minutes(self):
        value = self._pause_minutes() if callable(self._pause_minutes) else self._pause_minutes
        if type(value) is not int or not 1 <= value <= 240:
            raise ValueError("Account handoff duration must be an integer from 1 to 240 minutes")
        return value

    def read(self):
        if not self.path.exists():
            return {}
        state = json.loads(self.path.read_text("utf-8"))
        if not isinstance(state, dict):
            raise ValueError("Invalid account handoff state; refusing to bypass it")
        if state.get("phase") not in {"waiting", "resume_pending", "armed"}:
            raise ValueError("Invalid account handoff state; refusing to bypass it")
        if state["phase"] in {"waiting", "resume_pending"}:
            values = [state.get(key) for key in ("resume_after", "detected_at")]
            if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
                raise ValueError("Invalid account handoff deadline")
            if state["resume_after"] < state["detected_at"]:
                raise ValueError("Invalid account handoff deadline")
        return state

    def write(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2)
        fd, temporary = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(content)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def begin(self):
        state = self.read()
        if state.get("phase") in {"waiting", "resume_pending"}:
            return state
        now = self.clock()
        minutes = self.configured_minutes()
        state = {"phase": "waiting", "detected_at": now, "resume_after": now + minutes * 60,
                 "pause_minutes": minutes,
                 "reason": "other_device_login", "relogin_verified": False}
        self.write(state)
        return state

    def remaining(self):
        state = self.read()
        if state.get("phase") != "waiting":
            return 0
        minutes = self.configured_minutes()
        deadline = state["detected_at"] + minutes * 60
        if state["resume_after"] != deadline or state.get("pause_minutes") != minutes:
            state.update(resume_after=deadline, pause_minutes=minutes)
            self.write(state)
        return max(0, state["resume_after"] - self.clock())

    def block(self):
        if self.remaining() > 0:
            raise AccountYield("Account yielded to another device until the persisted deadline")

    def release(self):
        state = self.read()
        if state.get("phase") != "waiting" or self.remaining() > 0:
            return False
        state = self.read()
        state.update(phase="resume_pending", released_at=self.clock())
        self.write(state)
        return True

    def confirm_main(self):
        state = self.read()
        if state.get("phase") == "resume_pending":
            state.update(phase="armed", relogin_verified=True, main_confirmed_at=self.clock())
            self.write(state)
