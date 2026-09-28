import pytest

from tasks.Component.GeneralBattle.battle_wait import (
    BattleWait,
    BattleWaitPlan,
    HookSignal,
    runtime,
    battle_wait_options,
    battle_wait_strategy,
    _DEFAULT_PER_BATTLE,
)


@pytest.fixture(autouse=True)
def reset_battle_wait_plan(monkeypatch):
    monkeypatch.setattr(battle_wait_strategy, 'battle_wait_plan', None)
    monkeypatch.setattr(battle_wait_options, 'options', None)
    runtime.task_owner = None
    runtime.pub_ctx = None
    runtime.pri_ctx = {}


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


@pytest.mark.xfail(reason='battle_wait_with_strategy 尚未迁移到 runtime (runtime.current 已移除)', strict=False)
def test_setup_runs_before_the_wait_loop():
    class OrderedBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            self.events.append('screenshot')

        def _bw_setup_record(self, pub, pri):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_completion_finish(self, pub, pri):
            self.events.append('completion')
            pub.success = True
            return HookSignal.DONE

    battle_wait = OrderedBattleWait()
    plan = BattleWaitPlan('setup_record', 'completion_finish')

    assert battle_wait.battle_wait_with_strategy(battle_wait_plan=plan) is True
    assert battle_wait.events == ['setup', 'screenshot', 'completion']


@pytest.mark.xfail(reason='battle_wait_with_strategy 尚未迁移到 runtime (runtime.current 已移除)', strict=False)
def test_custom_hook_is_resolved_and_executed_in_the_configured_sequence():
    class CustomBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            pass

        def _bw_setup_record(self, pub, pri):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_yyy_record(self, pub, pri):
            self.events.append('yyy')
            return HookSignal.CONTINUE

        def _bw_completion_finish(self, pub, pri):
            self.events.append('completion')
            pub.success = True
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


# options 与 plan 同语义: 装饰器覆盖全局, with 临时覆盖并在退出时还原。
# 本测试锁定新拆分 API —— 策略装饰器只注入 plan, options 由 battle_wait_options
# 各自负责(装饰器=整份覆盖并跨调用还原, with=进入时 merge、退出还原)。
@pytest.mark.xfail(reason='battle_wait_with_strategy 尚未迁移到 runtime (runtime.current 已移除)', strict=False)
def test_options_decorator_and_with_are_scoped_to_the_current_call():
    received = []
    decorator_options = {
        'completion': {'source': 'decorator'},
        'success': {'excludes': ['C_REWARD_1']},
    }
    context_options = {
        'success': {'excludes': ['C_END_MESSAGE_RIGHT_TOP']},
    }

    strategy = battle_wait_strategy('setup_record', 'completion_record')

    class OptionBattleWait(BattleWait):
        def screenshot(self):
            pass

        def _bw_setup_record(self, pub, pri):
            return HookSignal.DONE

        def _bw_completion_record(self, pub, pri):
            received.append(pub.options)
            pub.success = True
            return HookSignal.DONE

        @strategy
        def battle_wait_plain(self, *args, **kwargs):
            return self.battle_wait_with_strategy(*args, **kwargs)

    battle_wait = object.__new__(OptionBattleWait)

    # ---- 场景 1: 装饰器 = 整份覆盖全局 ---- 
    opts_decorator = battle_wait_options(**decorator_options)

    class Decorated(OptionBattleWait):
        @opts_decorator
        @strategy
        def battle_wait(self, *args, **kwargs):
            return self.battle_wait_with_strategy(*args, **kwargs)

    decorated = object.__new__(Decorated)
    assert decorated.battle_wait() is True
    assert received[-1] == decorator_options
    # 跨调用还原: 槽位回到调用前的状态, 不残留到别处
    assert battle_wait_options.options is None

    # ---- 场景 2: with = 临时覆盖, 进入时与当前槽位 merge, 退出还原 ----
    with battle_wait_options(**context_options):
        assert battle_wait_options.options == context_options
        # 未装饰 options 的入口直接读当前槽位
        assert battle_wait.battle_wait_plain() is True
        assert received[-1] == context_options

    # 退出 with 后还原(需要 __exit__ 还原)
    assert battle_wait_options.options is None
    assert battle_wait.battle_wait_plain() is True
    assert received[-1] is None


# 跨任务(两个任务各自独立声明策略+options)场景。复现 script.py 的调度时序:
# 每个任务运行前用 load_module 重新执行自己的 script_task.py, 即"装饰器在任务
# 运行时才生效, 后加载的任务覆盖前者"。
# 契约: battle_wait_plan 与 options 都是全局槽位, 后加载装饰器整份覆盖;
# 正在运行的任务拿到的正是自己模块装饰器声明的配置。
def test_cross_task_decorators_switch_plan_and_keep_own_options():
    # 任务 A 的装饰器: 默认 success hook + 自己的 options
    strategy_a = battle_wait_strategy('success_default')
    opts_a = battle_wait_options(success={'market': 'task_a'})

    @opts_a
    @strategy_a
    def battle_wait_a(owner, *, battle_wait_plan, options=None):
        # 被装饰后 wrapper 会注入当前生效的 battle_wait_plan / options
        return battle_wait_plan, options

    # 任务 A 运行: 生效的应是它自己的 plan 和 options
    plan_a, options_a = battle_wait_a(object())
    assert options_a['success']['market'] == 'task_a'
    # A 装饰(模块加载)后, 全局生效 plan 是 A 的
    assert battle_wait_strategy.battle_wait_plan is plan_a

    # 任务 B 后加载并装饰: 不同 success hook + 不同的 options
    strategy_b = battle_wait_strategy(success='activity')
    opts_b = battle_wait_options(success={'market': 'task_b'})

    @opts_b
    @strategy_b
    def battle_wait_b(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    # 核心断言: B 装饰(加载)后, 全局生效 plan 切成 B 自己的
    assert battle_wait_strategy.battle_wait_plan is not plan_a
    plan_b, options_b = battle_wait_b(object())
    assert plan_b.success == 'activity'
    assert battle_wait_strategy.battle_wait_plan is plan_b
    assert options_b['success']['market'] == 'task_b'
    assert options_b['success'] == {'market': 'task_b'}


# 未声明 options 的任务不应继承上一个任务的 options —— 后加载者覆盖后,
# 使用自己 options 装饰器的任务只拿自己声明的; 无 options 声明则回 None,
# 避免任务链里的 options 漂移。
def test_cross_task_options_do_not_leak_between_tasks():
    # 任务 A: 声明 options → 覆盖全局
    strategy_a = battle_wait_strategy('success_default')
    opts_a = battle_wait_options(success={'market': 'task_a'})

    @opts_a
    @strategy_a
    def battle_wait_a(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    _, options_a = battle_wait_a(object())
    assert options_a['success']['market'] == 'task_a'

    # 任务 B: 声明自己的 options → 不残留 A 的任何键
    strategy_b = battle_wait_strategy(success='activity')
    opts_b = battle_wait_options(success={'market': 'task_b'})

    @opts_b
    @strategy_b
    def battle_wait_b(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan, options

    plan_b, options_b = battle_wait_b(object())
    assert plan_b.success == 'activity'
    assert options_b['success'] == {'market': 'task_b'}


# ------------------------------------------------------------------------------------------------------------------
# runtime: 自动装饰 hook, 注入单例 pub_ctx / 每 hook 的 pri_ctx, 三档状态 + options 分发。
# ------------------------------------------------------------------------------------------------------------------

def _make_runtime_probe():
    class RuntimeProbe(BattleWait):
        def __init__(self):
            self.calls = []

        def _bw_setup_probe(self, pub, pri):
            self.calls.append(('setup', pub, pri))
            return HookSignal.DONE

        def _bw_completion_probe(self, pub, pri):
            self.calls.append(('completion', pub, pri))
            return HookSignal.DONE

        def _bw_success_probe(self, pub, pri):
            self.calls.append(('success', pub, pri))
            return HookSignal.DONE

    return RuntimeProbe()


def test_runtime_injects_singleton_pub_and_per_hook_pri():
    battle_wait = _make_runtime_probe()

    getattr(battle_wait, '_bw_setup_probe')()
    getattr(battle_wait, '_bw_completion_probe')()

    _, setup_pub, setup_pri = battle_wait.calls[0]
    _, completion_pub, completion_pri = battle_wait.calls[1]

    # 所有 hook 共享同一个 pub_ctx
    assert setup_pub is runtime.pub_ctx
    assert completion_pub is runtime.pub_ctx
    # 每个 hook 持有自己的 pri_ctx, 互不共享
    assert setup_pri is runtime.pri_ctx['_bw_setup_probe']
    assert completion_pri is runtime.pri_ctx['_bw_completion_probe']
    assert setup_pri is not completion_pri


def test_runtime_preserves_function_name_for_completion_detection():
    battle_wait = _make_runtime_probe()
    hook = getattr(battle_wait, '_bw_completion_probe')
    assert hook.__name__ == '_bw_completion_probe'


def test_runtime_task_owner_switch_resets_per_task():
    battle_wait = _make_runtime_probe()
    getattr(battle_wait, '_bw_setup_probe')()
    runtime.pub_ctx.cross['keep'] = 1
    runtime.pub_ctx.per_task['drop'] = 1
    runtime.pri_ctx['_bw_setup_probe'].per_task['drop'] = 1

    # 换一个 owner 触发 reset_per_task: cross 保留, per_task 清空
    other = _make_runtime_probe()
    getattr(other, '_bw_setup_probe')()

    assert runtime.pub_ctx.cross == {'keep': 1}
    assert runtime.pub_ctx.per_task == {}
    assert runtime.pri_ctx['_bw_setup_probe'].per_task == {}


def test_runtime_reset_per_battle_keeps_cross_and_per_task():
    battle_wait = _make_runtime_probe()
    getattr(battle_wait, '_bw_setup_probe')()
    runtime.pub_ctx.cross['c'] = 1
    runtime.pub_ctx.per_task['t'] = 1
    runtime.pub_ctx.per_battle['b'] = 1
    runtime.pri_ctx['_bw_setup_probe'].per_battle['b'] = 1

    runtime.reset_per_battle()

    assert runtime.pub_ctx.cross == {'c': 1}
    assert runtime.pub_ctx.per_task == {'t': 1}
    assert runtime.pub_ctx.per_battle == _DEFAULT_PER_BATTLE()
    assert 'b' not in runtime.pub_ctx.per_battle
    assert runtime.pri_ctx['_bw_setup_probe'].per_battle == {}


def test_runtime_update_options_distributes_by_hook_event_name():
    battle_wait = _make_runtime_probe()
    getattr(battle_wait, '_bw_setup_probe')()
    getattr(battle_wait, '_bw_completion_probe')()
    getattr(battle_wait, '_bw_success_probe')()

    runtime.update_options({
        'setup': {'x': 1},
        'completion': {'y': 2},
        'success': {'z': 3},
    })

    # pub 拿整份 options
    assert runtime.pub_ctx.options['setup'] == {'x': 1}
    # 每个 hook 的 pri 只拿自己事件名对应的 slice
    assert runtime.pri_ctx['_bw_setup_probe'].options == {'x': 1}
    assert runtime.pri_ctx['_bw_completion_probe'].options == {'y': 2}
    assert runtime.pri_ctx['_bw_success_probe'].options == {'z': 3}


def test_runtime_update_options_none_clears_all_slices():
    battle_wait = _make_runtime_probe()
    getattr(battle_wait, '_bw_setup_probe')()
    runtime.update_options({'setup': {'x': 1}})
    assert runtime.pub_ctx.options['setup'] == {'x': 1}

    runtime.update_options(None)

    assert runtime.pub_ctx.options == {}
    assert runtime.pri_ctx['_bw_setup_probe'].options == {}


def test_runtime_str_shows_hook_name_and_scope_keys():
    battle_wait = _make_runtime_probe()
    getattr(battle_wait, '_bw_setup_probe')()
    runtime.pub_ctx.per_task['stage'] = 1
    runtime.pri_ctx['_bw_setup_probe'].per_battle['clicked'] = True
    runtime.update_options({'setup': {'x': 1}})

    text = str(battle_wait.__class__._bw_setup_probe)

    assert '_bw_setup_probe' in text
    assert 'stage' in text
    assert 'clicked' in text
    assert 'setup' in text
