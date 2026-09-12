import pytest

from tasks.Component.GeneralBattle.battle_wait import (
    BattleWait,
    BattleWaitPlan,
    HookSignal,
    battle_wait_strategy,
)


@pytest.fixture(autouse=True)
def reset_battle_wait_plan(monkeypatch):
    monkeypatch.setattr(battle_wait_strategy, 'battle_wait_plan', None)
    monkeypatch.setattr(battle_wait_strategy, 'options', None)


def test_default_plan_contains_default_hooks_and_sequence():
    plan = BattleWaitPlan()

    assert tuple(getattr(plan, hook) for hook in BattleWaitPlan.HOOKS_DEFAULT) == (
        'default',
        'default',
        'default',
        'default',
        'default',
        'default',
    )
    assert plan.sequence == 'completion>interrupt>success>failure>idle'
    assert plan.function_setup_name == '_bw_setup_default'


def test_decorator_passes_its_plan_to_the_wrapped_function():
    strategy = battle_wait_strategy('reserve_default', 'idle_default', failure='custom')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    plan = battle_wait(object())

    assert plan.reserve == 'default'
    assert plan.idle == 'default'
    assert plan.failure == 'custom'


def test_with_context_uses_a_temporary_plan_and_restores_the_default_plan():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    default_plan = battle_wait_strategy.battle_wait_plan

    with battle_wait_strategy('success_default', failure='custom'):
        temporary_plan = battle_wait(object())
        assert temporary_plan.failure == 'custom'

    assert battle_wait_strategy.battle_wait_plan is default_plan
    assert battle_wait(object()) is default_plan


def test_event_and_strategy_can_be_configured_with_both_supported_forms():
    plan = BattleWaitPlan('yyy_default', abcd='edf')

    assert plan.yyy == 'default'
    assert plan.abcd == 'edf'
    assert plan.sequence_function_names()[4:6] == [
        '_bw_yyy_default',
        '_bw_abcd_edf',
    ]


def test_an_event_cannot_be_configured_with_two_strategies():
    with pytest.raises(ValueError, match="configured more than once"):
        BattleWaitPlan('success_default', success='custom')


def test_setup_runs_before_the_wait_loop():
    class OrderedBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            self.events.append('screenshot')

        def _bw_setup_record(self, bw_ctx):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_completion_finish(self, bw_ctx):
            self.events.append('completion')
            bw_ctx.success = True
            return HookSignal.DONE

    battle_wait = OrderedBattleWait()
    plan = BattleWaitPlan('setup_record', 'completion_finish')

    assert battle_wait.battle_wait_with_strategy(battle_wait_plan=plan) is True
    assert battle_wait.events == ['setup', 'screenshot', 'completion']


def test_custom_hook_is_resolved_and_executed_in_the_configured_sequence():
    class CustomBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            pass

        def _bw_setup_record(self, bw_ctx):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_yyy_record(self, bw_ctx):
            self.events.append('yyy')
            return HookSignal.CONTINUE

        def _bw_completion_finish(self, bw_ctx):
            self.events.append('completion')
            bw_ctx.success = True
            return HookSignal.DONE

    battle_wait = CustomBattleWait()
    plan = BattleWaitPlan(
        'setup_record',
        'yyy_record',
        'completion_finish',
        sequence='yyy > completion > interrupt > success > failure > idle',
    )

    assert battle_wait.battle_wait_with_strategy(battle_wait_plan=plan) is True
    assert battle_wait.events == ['setup', 'yyy', 'completion']


def test_custom_sequence_controls_hook_order():
    plan = BattleWaitPlan(
        'yyy_default',
        sequence='failure > yyy > completion > interrupt > success > idle',
    )

    assert plan.sequence_function_names() == [
        '_bw_failure_default',
        '_bw_yyy_default',
        '_bw_completion_default',
        '_bw_interrupt_default',
        '_bw_success_default',
        '_bw_idle_default',
    ]


def test_custom_events_without_sequence_are_inserted_before_idle_in_argument_order():
    plan = BattleWaitPlan('yyy_default', 'abcd_edf')

    assert plan.sequence == 'completion>interrupt>success>failure>yyy>abcd>idle'


def test_dynamic_override_does_not_modify_the_default_plan():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    default_plan = battle_wait_strategy.battle_wait_plan

    overridden_plan = battle_wait(object(), random_click_swipt_enable=True)

    assert overridden_plan is not default_plan
    assert overridden_plan.randomclick == 'default'
    assert not hasattr(default_plan, 'randomclick')
    assert battle_wait_strategy.battle_wait_plan is default_plan


def test_dynamic_override_is_only_valid_for_the_current_call():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    battle_wait(object(), random_click_swipt_enable=True)
    plan_without_override = battle_wait(object(), random_click_swipt_enable=False)

    assert not hasattr(plan_without_override, 'randomclick')


# options 与 plan 同语义: 装饰器覆盖全局, with_options 临时覆盖并在退出时还原(__exit__ 还原 _previous_options)。
# 本测试同时锁定 __exit__ 的还原行为 —— 若还原缺失, 最后一组断言会失败。
def test_decorator_options_and_with_options_are_scoped_to_the_current_call():
    received_options = []
    decorator_options = {
        'completion': {'source': 'decorator'},
        'success': {'excludes': ['C_REWARD_1']},
    }
    context_options = {
        'success': {'excludes': ['C_END_MESSAGE_RIGHT_TOP']},
    }

    strategy = battle_wait_strategy(
        'setup_record', 'completion_record', options=decorator_options
    )

    class OptionBattleWait(BattleWait):
        def screenshot(self):
            pass

        def _bw_setup_record(self, bw_ctx):
            return HookSignal.DONE

        def _bw_completion_record(self, bw_ctx):
            received_options.append(bw_ctx.options)
            bw_ctx.success = True
            return HookSignal.DONE

        @strategy
        def battle_wait(self, *args, **kwargs):
            return self.battle_wait_with_strategy(*args, **kwargs)

    battle_wait = object.__new__(OptionBattleWait)

    # 装饰器覆盖全局: 调用方拿到装饰器的整份 options
    assert battle_wait.battle_wait() is True
    assert received_options[-1] == decorator_options

    with strategy.with_options(context_options):
        # with 是整份覆盖, 不是合并: 装饰器的 completion 键也被覆盖掉
        assert battle_wait.battle_wait() is True
        assert received_options[-1] == context_options
        strategy_text = str(strategy)
        assert 'options=' in strategy_text
        assert 'C_END_MESSAGE_RIGHT_TOP' in strategy_text

    # 退出 with 后还原为装饰器覆盖的那份(需要 __exit__ 还原 _previous_options)
    assert battle_wait.battle_wait() is True
    assert received_options[-1] == decorator_options
    assert 'C_REWARD_1' in str(strategy)


# 跨任务(两个装饰器)场景。复现 script.py 的调度时序: 每个任务运行前用 load_module
# 重新执行自己的 script_task.py, 即"装饰器在任务运行时才生效, 后加载的任务覆盖前者"。
# 契约: options 与 battle_wait_plan 语义完全一致 —— 都是全局槽位, 后加载装饰器整份覆盖,
# 正在运行的任务拿到的正是自己模块装饰器声明的配置。
def test_cross_task_decorators_switch_plan_and_keep_own_options():
    # 任务 A 的装饰器: 默认 success hook + 自己的 options
    strategy_a = battle_wait_strategy(
        'success_default',
        options={'success': {'market': 'task_a'}},
    )

    @strategy_a
    def battle_wait_a(owner, *, battle_wait_plan, options=None):
        # 被装饰后 wrapper 会注入当前生效的 battle_wait_plan / options, 这里原样抛回来断言
        return battle_wait_plan, options

    # 任务 A 运行: 生效的应是它自己的 plan 和 options
    plan_a, options_a = battle_wait_a(object())
    assert plan_a.success == 'default'
    assert options_a['success']['market'] == 'task_a'
    # A 装饰(模块加载)后, 全局生效 plan 和 options 都是 A 的
    assert battle_wait_strategy.battle_wait_plan is plan_a
    assert battle_wait_strategy.options['success']['market'] == 'task_a'

    # 任务 B 后加载并装饰: 不同 success hook + 不同的 options → 整份覆盖全局
    strategy_b = battle_wait_strategy(
        success='activity',
        options={'success': {'market': 'task_b'}},
    )

    @strategy_b
    def battle_wait_b(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    # 核心断言 1: B 装饰(加载)后, 全局生效 plan 和 options 都切成 B 自己的
    assert battle_wait_strategy.battle_wait_plan is not plan_a
    plan_b, options_b = battle_wait_b(object())
    assert plan_b.success == 'activity'
    assert battle_wait_strategy.battle_wait_plan is plan_b
    assert options_b['success']['market'] == 'task_b'
    assert battle_wait_strategy.options['success']['market'] == 'task_b'

    # 观察 A 的"滞后"行为: 此刻全局已被 B 覆盖, A 再次调用跟随全局(B 的),
    # options 和 plan 一样是"后加载者胜", 不再保留 A 自己的。
    plan_a2, options_a2 = battle_wait_a(object())
    assert plan_a2 is plan_b
    assert options_a2['success']['market'] == 'task_b'


# 未声明 options 的装饰器应重置回 _DEFAULT_OPTIONS, 而不是继承上一个任务的 options。
# 这是"后加载者覆盖 + 未声明回默认"的兜底, 避免任务链里的 options 漂移。
def test_cross_task_options_do_not_leak_between_tasks():
    # 任务 A: 声明 options → 覆盖全局
    strategy_a = battle_wait_strategy(
        'success_default',
        options={'success': {'market': 'task_a'}},
    )

    @strategy_a
    def battle_wait_a(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    _, options_a = battle_wait_a(object())
    assert options_a['success']['market'] == 'task_a'

    # 任务 B: 不声明 options → __call__ 重置回 _DEFAULT_OPTIONS, 不残留 A 的
    strategy_b = battle_wait_strategy(success='activity')

    @strategy_b
    def battle_wait_b(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    plan_b, options_b = battle_wait_b(object())
    assert plan_b.success == 'activity'
    assert 'task_a' not in options_b.get('success', {})
    # 全局槽位也跟着回到默认(与 plan 的"后加载者覆盖"一致)
    assert battle_wait_strategy.options == battle_wait_strategy._DEFAULT_OPTIONS
    assert options_b == battle_wait_strategy._DEFAULT_OPTIONS
