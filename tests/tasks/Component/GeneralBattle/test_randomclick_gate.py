import time

import pytest

from tasks.Component.GeneralBattle.battle_wait import (
    HookSignal,
    OptionRandomclickDefault,
    PerBattleRandomclick,
    PerTaskRandomclick,
    PrivateContext,
    PublicContext,
    randomclick_gate,
)


class FakeSelf:
    in_battle = True
    calls = 0

    def is_in_battle(self, is_screenshot=False):
        return self.in_battle

    def click(self, *args, **kwargs):
        self.calls += 1

    def swipe(self, *args, **kwargs):
        self.calls += 1


def make_pub(options=None):
    options = options if options is not None else OptionRandomclickDefault()
    return PublicContext(options={'randomclick': options})


def make_pri(per_battle=None, per_task=None):
    return PrivateContext(
        per_battle=per_battle if per_battle is not None else PerBattleRandomclick(),
        per_task=per_task if per_task is not None else PerTaskRandomclick(),
    )


def make_gate():
    fake = FakeSelf()

    @randomclick_gate
    def _bw_randomclick_default(self, pub, pri):
        self.calls += 1
        return HookSignal.CONTINUE

    return fake, _bw_randomclick_default


def test_type_mismatch_raises():
    fake, gate = make_gate()

    with pytest.raises(TypeError, match='OptionRandomclick'):
        gate(fake, PublicContext(options={'randomclick': {'bad': 1}}), make_pri())

    with pytest.raises(TypeError, match='PerBattleRandomclick'):
        pub = make_pub()
        gate(fake, pub, PrivateContext(per_battle={}, per_task=PerTaskRandomclick()))

    with pytest.raises(TypeError, match='PerTaskRandomclick'):
        pub = make_pub()
        gate(fake, pub, PrivateContext(per_battle=PerBattleRandomclick(), per_task={}))


def test_not_in_battle_skips():
    fake, gate = make_gate()
    fake.in_battle = False

    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(0.0, 0.0), trigger_probability=1.0))
    pri = make_pri()
    pri.per_battle.first_allowed_time = time.time() - 10  # 已过 delay
    pri.per_battle.execution_limit_resolved = 5

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0


def test_first_call_resolves_delay_and_limit():
    fake, gate = make_gate()
    pub = make_pub()
    pri = make_pri()

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0
    assert 5.0 <= pri.per_battle.start_delay_resolved <= 10.0
    assert 1 <= pri.per_battle.execution_limit_resolved <= 2
    assert pri.per_battle.first_allowed_time > 0.0


def test_start_delay_blocks_until_first_allowed_time():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(100.0, 100.0)))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 100.0
    pri.per_battle.execution_limit_resolved = 5
    pri.per_battle.first_allowed_time = time.time() + 100.0

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0


def test_execution_limit_blocks_after_count_reached():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(0.0, 0.0), trigger_probability=1.0))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 1
    pri.per_battle.first_allowed_time = time.time() - 10
    pri.per_battle.execution_count = 1

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0


def test_cooldown_blocks_within_cooling_window():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(9999.0, 9999.0), trigger_probability=1.0))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 5
    pri.per_battle.first_allowed_time = time.time() - 10
    pri.per_task.last_attempt_time = time.time()

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0


def test_cooldown_records_attempt_even_when_probability_blocked():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(0.0, 0.0), trigger_probability=0.0))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 5
    pri.per_battle.first_allowed_time = time.time() - 10
    pri.per_task.last_attempt_time = time.time() - 9999

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0
    # 概率未通过也算一次尝试，cooldown 周期被刷新
    assert pri.per_task.last_attempt_time > time.time() - 1


def test_cooldown_survives_reset_per_battle():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(9999.0, 9999.0), trigger_probability=1.0))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 5
    pri.per_battle.first_allowed_time = time.time() - 10

    # 上一场战斗刚尝试过 → last_attempt_time 在 per_task 保留
    pri.per_task.last_attempt_time = time.time()

    # 模拟新一场战斗: per_battle 更新, per_task 不变
    pri.per_battle = PerBattleRandomclick()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 5
    pri.per_battle.first_allowed_time = time.time() - 10

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 0


def test_all_gates_pass_executes_once_and_increments():
    fake, gate = make_gate()
    pub = make_pub(OptionRandomclickDefault(start_delay=(0.0, 0.0), cooldown=(0.0, 0.0), trigger_probability=1.0))
    pri = make_pri()
    pri.per_battle.start_delay_resolved = 0.0
    pri.per_battle.execution_limit_resolved = 3
    pri.per_battle.first_allowed_time = time.time() - 10
    pri.per_task.last_attempt_time = time.time() - 9999

    result = gate(fake, pub, pri)

    assert result == HookSignal.CONTINUE
    assert fake.calls == 1
    assert pri.per_battle.execution_count == 1
    # cooldown 周期刷新
    assert pri.per_task.last_attempt_time > time.time() - 1