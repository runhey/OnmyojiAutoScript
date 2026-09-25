"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         battle_wait.py  调用链地图                               ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  装饰器双层栈(任务级)
  ───────────────────────────────────────────────────────────────────
  @battle_wait_options(excludes=[...])   ← 覆盖 options
  @battle_wait_strategy(success='activity') ← 覆盖 plan
       ↓
  script_task.battle_wait()
       ↓
  ┌─────────────────────────────────────────────────────────┐
  │ battle_wait_options.__call__.inner                      │
  │   options → pub.options                                  │
  │   finally: 还原 class options                            │
  └───────────────────────────┬─────────────────────────────┘
                              ↓
  ┌─────────────────────────────────────────────────────────┐
  │ battle_wait_strategy.__call__.inner                     │
  │   current_plan = deepcopy(类 plan).override(kwargs)      │
  │   runtime.reset_per_battle()   ← 每场新状态              │
  │   runtime.update_options()     ← 按事件切片到各 pri      │
  └───────────────────────────┬─────────────────────────────┘
                              ↓
  ┌─────────────────────────────────────────────────────────┐
  │ battle_wait_with_strategy(plan)                          │
  │                                                          │
  │   setup hook ──────────────────────── run 一次           │
  │   hook_enabled = sequence events − {completion}          │
  │                                                          │
  │   ┌─── while True ─────────────────────────────────┐    │
  │   │  screenshot()                                   │    │
  │   │  for handler in sequence顺序:                   │    │
  │   │      if event not in hook_enabled: skip         │    │
  │   │      result = handler()  ──┐                    │    │
  │   │          ↓                 │                    │    │
  │   │      DONE  ────────────────┤  结束循环           │    │
  │   │      CONTINUE ──→ 下一个 handler               │    │
  │   │                                                   │    │
  │   │  success/failure 结算后:                          │    │
  │   │    per_battle['success'] = BattleResult.X         │    │
  │   │    enable=('completion',)  ← completion 开门      │    │
  │   └───────────────────────────────────────────────────┘    │
  │                                                          │
  │   return per_battle['success'] == BattleResult.SUCCESS   │
  └─────────────────────────────────────────────────────────┘

  ┌──────────────────── Hook 调用 ────────────────────────────┐
  │ BattleWait.__new__  遍历 MRO, _bw_* → runtime 包装       │
  │ handler()                                                      │
  │   → runtime.__call__(owner)                                    │
  │     → func(owner, pub=pub_ctx, pri=pri_ctx[hook_name])        │
  └───────────────────────────────────────────────────────────────┘

  ┌──────────────────── 数据流 ─────────────────────────────────┐
  │                                                             │
  │  battle_wait_options.options  (类槽, 装饰器/with 写入)     │
  │        ↓ pub.options = 上面整个                              │
  │        ↓ pri[hook].options = 按事件名切片                   │
  │                                                             │
  │  pub (全局)          pri (每个 hook 各一份)                 │
  │  ├─ cross             ├─ cross                               │
  │  ├─ per_task          ├─ per_task                            │
  │  ├─ per_battle        ├─ per_battle                          │
  │  │   ├─ success       │                                     │
  │  │   └─ hook_enabled  │                                     │
  │  └─ options           └─ options(本事件切片)                │
  │                                                             │
  │  生命周期:                                                  │
  │    reset_per_task    runtime 首次遇到新 task_owner           │
  │    reset_per_battle  每次 battle_wait_strategy.__call__     │
  └─────────────────────────────────────────────────────────────┘
"""

import random
import time
import copy
import math
from copy import deepcopy


from functools import wraps, update_wrapper
from dataclasses import dataclass, field, fields
from typing import TypeVar, ParamSpec, Callable
from enum import Enum, auto
from cached_property import cached_property

from module.logger import logger
from module.base.timer import Timer
from module.atom.click import RuleClickExclude
from module.atom.image import RuleImage
from module.base.utils import get_color, color_similar

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType


P = ParamSpec('P')
T = TypeVar('T')


class HookSignal(Enum):
    CONTINUE = auto()  # 无事发生
    BUSY = auto()  # 处理了，继续
    DONE = auto()  # 流程结束


class BattleResult(Enum):
    SUCCESS = auto()
    FAILURE = auto()


# ─── 默认值常量 ───────────────────────────────────
# 战斗 hook 事件列表 & 默认调用顺序
_HOOKS_DEFAULT: tuple[str, ...] = (
    'setup', 'completion', 'interrupt', 'prepare', 'preset', 'green', 'red', 'echo', 'success', 'failure', 'idle',
)
_SEQUENCE_DEFAULT: str = 'completion > interrupt > prepare > preset > green > red > echo > success > failure >'

# 跨任务/跨战斗状态的初始
@dataclass
class PerTaskState:
    """跨任务状态, 单个任务全程共享, reset_per_task 时重建"""
    count: int = 0


@dataclass
class PerBattleState:
    """跨战斗状态, 每场战斗独立, reset_per_battle 时重建"""
    success: BattleResult = BattleResult.FAILURE
    hook_enabled: set = field(default_factory=lambda: set(_HOOKS_DEFAULT) - {'completion'})


# 每个 hook 事件的 options 数据类: pri[hook].options 就是这个实例。
# 按 event 建模 —— 不管 success 挂的是什么 strategy, OptionSuccessDefault 都是它的配置。
@dataclass
class OptionSetupDefault:
    excludes: list | None = None


@dataclass
class OptionCompletionDefault:
    # 这里是为了， 确认结束战斗后退回到 “fire” 的界面
    check_imgs: list[RuleImage] = None
    # 兜底：check_imgs 都检测不到时，间隔点击的排除位
    excludes: list[str] = field(default_factory=list)


@dataclass
class OptionInterruptDefault:
    pass


@dataclass
class OptionSuccessDefault:
    excludes_1: list[str] = field(default_factory=lambda:
    [
        'C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1',
        'C_END_BUFF_AREA_2', 'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
    ])
    excludes_2: list[str] = field(default_factory=lambda:
    [
        'C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1',
        'C_END_BUFF_AREA_2', 'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
        'C_END_1_1', 'C_END_1_2', 'C_END_1_3', 'C_END_1_4',
        'C_END_1_5', 'C_END_1_6',
    ])


@dataclass
class OptionFailureDefault:
    pass


@dataclass
class OptionIdleDefault:
    pass


@dataclass
class OptionPrepareDefault:
    lock_team: bool = False


@dataclass
class OptionPresetDefault:
    preset_enable: bool = False
    preset_group: int = 1
    preset_team: int = 1


@dataclass
class OptionGreenDefault:
    green_enable: bool = False
    green_mark: GreenMarkType = GreenMarkType.GREEN_LEFT1


@dataclass
class OptionRedDefault:
    pass


@dataclass
class OptionEchoDefault:
    pass


@dataclass
class OptionRandomclickDefault:
    # 战斗开始后，首次允许执行前等待多久 每次战斗重抽存状态到 per_battle.start_delay_resolved
    start_delay: tuple[float, float] = (5.0, 10.0)
    # 两次执行之间的最小间隔, 每次执行的时候随机选一个，不存状态, 这个时间包括战斗结束后到下一轮的时间哈
    cooldown: tuple[float, float] = (30.0, 60.0)
    # 到达可执行时间后，本次实际执行的概率
    trigger_probability: float = 0.6
    # 本场战斗最多执行几次；元组表示开场时随机取一个上限， 每次战斗重抽一次，存状态到per_battle.execution_limit_resolved
    execution_limit: tuple[int, int] = (1, 2)

    def expected_random_clicks(
            self,
            battle_seconds: float = 30.0,
            gap_seconds: float = 10.0,
            battles: int = 100
    ) -> float:
        """估算多场战斗累计的期望随机动作执行次数（稳态解析模型）。

        实际触发	14/115 ≈ 12.2%	swipe 8 + random_click 6，平均约每 8.2 场实操一次
        模型预测	单场 0.125 → 115 场 ≈ 14.4 次 (12.5%)	expected_random_clicks(8.75, 6.24, 115)
        这行是统计数据： 实际战斗时间，约 7.0 ~ 7.7 s：约 30 场，约 8.9 ~ 10.2 s：约 85 场。gap时间平均gap	约 6.24 s。 整体周期均值8.75 + 6.24 ≈ 15.0 s

        Args:
            battle_seconds: 单场战斗的持续时间（秒）。
            gap_seconds: 战斗结束到下一轮战斗的间隔（秒），冷却在该时段内持续流逝。
            battles: 统计的战斗场数。

        Returns:
            累计 battles 场的期望随机动作执行次数。
        """
        cooldown_low, cooldown_high = self.cooldown
        cooldown_window_mean = cooldown_low + (math.sqrt(math.pi) / 2) * math.sqrt(cooldown_high - cooldown_low)
        start_delay_low, start_delay_high = self.start_delay
        start_delay_mean = (start_delay_low + start_delay_high) / 2
        attempts_per_battle = (battle_seconds + gap_seconds - start_delay_mean) / cooldown_window_mean
        attempts_can_execute = self.trigger_probability * attempts_per_battle
        attempts_can_execute_exp = math.exp(-attempts_can_execute)
        # 这里建模成泊松分布
        limit_low, limit_high = self.execution_limit
        per_battle = 0.0
        for limit in range(limit_low, limit_high + 1):
            probability_below = attempts_can_execute_exp  # P(成功次数 < k)
            expected_with_limit = 0.0
            # E[min(H, limit)] = Σ_{k=1}^{limit} P(成功次数 ≥ k)
            for k in range(1, limit + 1):
                expected_with_limit += 1 - probability_below
                probability_below += attempts_can_execute_exp * attempts_can_execute ** k / math.factorial(k)
            per_battle += expected_with_limit
        per_battle /= limit_high - limit_low + 1
        return per_battle * battles


# event → options 数据类, update_options 靠它按 hook2event 自动实例化分发
_OPTION_CLASSES: dict[str, type] = {
    'setup': OptionSetupDefault,
    'completion': OptionCompletionDefault,
    'interrupt': OptionInterruptDefault,
    'success': OptionSuccessDefault,
    'failure': OptionFailureDefault,
    'idle': OptionIdleDefault,
    'prepare': OptionPrepareDefault,
    'preset': OptionPresetDefault,
    'green': OptionGreenDefault,
    'red': OptionRedDefault,
    'echo': OptionEchoDefault,
    'randomclick': OptionRandomclickDefault,
}


def _options_to_instances(raw: dict) -> dict:
    """把按 event 分组的原始 dict 转成对应的 Option 数据类实例（未知 key 过滤）"""
    result = {}
    for event, value in (raw or {}).items():
        opt_cls = _OPTION_CLASSES.get(event)
        if opt_cls is not None and isinstance(value, opt_cls):
            result[event] = value
        elif opt_cls is not None and isinstance(value, dict):
            known = {k: v for k, v in value.items() if k in opt_cls.__dataclass_fields__}
            result[event] = opt_cls(**known)
        else:
            result[event] = deepcopy(value)
    return result


# pri 层的私有状态, 同样按 event 建模: pri[hook].per_task / per_battle 就是这个实例。
# 字段按需声明 —— 有自定义私有状态的 strategy 往自己 event 的类里加字段。
@dataclass
class PerTaskSetup:
    pass


@dataclass
class PerTaskCompletion:
    pass


@dataclass
class PerTaskInterrupt:
    pass


@dataclass
class PerTaskSuccess:
    pass


@dataclass
class PerTaskFailure:
    pass


@dataclass
class PerTaskIdle:
    pass


@dataclass
class PerTaskPrepare:
    pass


@dataclass
class PerTaskPreset:
    # 一次任务类型触发一次，想要再次触发把done设置False
    done: bool = False


@dataclass
class PerTaskGreen:
    pass


@dataclass
class PerTaskRed:
    pass


@dataclass
class PerTaskEcho:
    pass


@dataclass
class PerTaskRandomclick:
    # 上一次点击的时间
    last_attempt_time: float = 0.0


@dataclass
class PerBattleSetup:
    pass


@dataclass
class PerBattleCompletion:
    click_stage_2: RuleClickExclude | None = None
    # 兜底点击节拍器：进入 completion 起算，满 8s 才首次点击，之后每 8s 一次
    fallback_timer: Timer | None = None


@dataclass
class PerBattleInterrupt:
    pass


@dataclass
class PerBattleSuccess:
    click_stage_1: RuleClickExclude | None = None
    click_stage_2: RuleClickExclude | None = None

    @classmethod
    def reward_exclude_click(
            cls,
            onwer,
            areas: list[str] = None,
            name: str = 'success_exclude_click'
    ) -> RuleClickExclude:
        inputs = []
        for area in areas:
            click = getattr(onwer, area, None)
            if click is None:
                raise ValueError(f'Unknown success exclusion click: {area!r}')
            inputs.append(click)
        return RuleClickExclude(inputs, name=name)


@dataclass
class PerBattleFailure:
    pass


@dataclass
class PerBattleIdle:
    pass


@dataclass
class PerBattlePrepare:
    done: bool = False
    timer: Timer = None


@dataclass
class PerBattlePreset:
    pass


@dataclass
class PerBattleGreen:
    # 本场战斗完成
    done: bool = False


@dataclass
class PerBattleRed:
    pass


@dataclass
class PerBattleEcho:
    pass


@dataclass
class PerBattleRandomclick:
    # 本场战斗已执行的随机动作次数
    execution_count: int = 0
    # 本场战斗的执行次数上限，首次拦截时从 execution_limit 随机解析
    execution_limit_resolved: int = 0
    # 本场战斗的首次执行延迟，首次拦截时从 start_delay 随机解析
    start_delay_resolved: float = 0.0
    # 首次允许执行的时间戳（0.0 表示尚未解析，首次拦截时写入）
    first_allowed_time: float = 0.0


# event → pri 私有状态数据类
_PER_TASK_CLASSES: dict[str, type] = {
    'setup': PerTaskSetup,
    'completion': PerTaskCompletion,
    'interrupt': PerTaskInterrupt,
    'success': PerTaskSuccess,
    'failure': PerTaskFailure,
    'idle': PerTaskIdle,
    'prepare': PerTaskPrepare,
    'preset': PerTaskPreset,
    'green': PerTaskGreen,
    'red': PerTaskRed,
    'echo': PerTaskEcho,
    'randomclick': PerTaskRandomclick,
}

_PER_BATTLE_CLASSES: dict[str, type] = {
    'setup': PerBattleSetup,
    'completion': PerBattleCompletion,
    'interrupt': PerBattleInterrupt,
    'success': PerBattleSuccess,
    'failure': PerBattleFailure,
    'idle': PerBattleIdle,
    'prepare': PerBattlePrepare,
    'preset': PerBattlePreset,
    'green': PerBattleGreen,
    'red': PerBattleRed,
    'echo': PerBattleEcho,
    'randomclick': PerBattleRandomclick,
}

# ────────────────────────────────────────────



class BattleWaitPlan:
    """
    就是一个超级大的状态机，这里拆成了很多hook
    """
    HOOKS_DEFAULT = _HOOKS_DEFAULT
    SEQUENCE_DEFAULT = _SEQUENCE_DEFAULT

    def __init__(self, *arg, **kwargs):
        extra_sequence: str = ''
        #
        for event_strategy in arg:
            if not isinstance(event_strategy, str):
                raise TypeError(
                    'Battle wait hook must be a string in '
                    '"event_strategy" format; '
                    f'got {event_strategy!r}'
                )

            if not event_strategy:
                raise ValueError(
                    'Battle wait hook cannot be empty; '
                    'expected "event_strategy" format'
                )
            event, separator, strategy = event_strategy.partition('_')
            if not separator or not event or not strategy:
                raise ValueError(
                    'Invalid battle wait hook '
                    f'{event_strategy!r}; expected "event_strategy" format'
                )
            setattr(self, event, strategy)
            if event not in self.HOOKS_DEFAULT:
                extra_sequence += f'{event} > '

        #
        for event, strategy in kwargs.items():
            if not event or not isinstance(event, str) or not isinstance(strategy, str):
                raise TypeError(f'{event} or {strategy} is not a string')
            if getattr(self, event, None) is not None:
                raise ValueError(
                    f'Battle wait event {event!r} was configured more than once'
                )
            setattr(self, event, strategy)
            if event not in self.HOOKS_DEFAULT:
                extra_sequence += f'{event} > '

        # 补齐默认的
        for event in self.HOOKS_DEFAULT:
            if getattr(self, event, None) is None:
                setattr(self, event, 'default')

        #
        self.sequence = kwargs.get('sequence', None)
        if self.sequence is None:
            self.sequence = f'{BattleWaitPlan.SEQUENCE_DEFAULT} {extra_sequence} idle'
        if not isinstance(self.sequence, str):
            raise TypeError(
                'Battle wait sequence must be a string containing event names '
                "separated by '>'; "
                f'got {self.sequence!r}'
            )
        self.sequence: str = self.sequence.replace(' ', '').replace('\n', '').replace('\r', '').replace('setup', '')
        for event_name in self.sequence.split('>'):
            event_name = event_name.strip()
            if event_name == "sequence":
                continue
            if getattr(self, event_name, None) is None:
                raise ValueError(
                    f'Unknown battle wait event {event_name!r} in '
                    f'sequence {self.sequence!r}'
                )
        for event in self.HOOKS_DEFAULT:
            if event != 'setup' and  event not in self.sequence:
                raise ValueError(
                    f'Battle wait sequence is missing required event {event!r}; '
                    f'got {self.sequence!r}'
                )

    def __str__(self):
        lines = [f"{self.__class__.__name__}:", f"  sequence: {self.sequence}", "  hooks:"]
        for event_name in self.HOOKS_DEFAULT:
            strategy_name = getattr(self, event_name, None)
            if callable(strategy_name):
                if hasattr(strategy_name, '__name__'):
                    func_name = strategy_name.__name__
                else:
                    func_name = repr(strategy_name)
                val_str = f"<function {func_name}>"
            else:
                val_str = repr(strategy_name)
            lines.append(f"    {event_name}: {val_str}")
        return "\n".join(lines)

    def __repr__(self):
        return self.__str__()

    @property
    def function_setup_name(self) -> str:
        if getattr(self, 'setup', None) is None:
            self.setup = 'default'
        return f'_bw_setup_{self.setup}'

    def sequence_function_names(self) -> list[str]:
        """
         注意，这里是没有setup的
        """
        function_names = []
        for event_name in self.sequence.split('>'):
            event_name = event_name.strip()
            if not event_name:
                continue

            if not hasattr(self, event_name):
                raise ValueError(f'Unknown battle wait event: {event_name}')

            strategy_name = getattr(self, event_name)
            if not isinstance(strategy_name, str) or not strategy_name:
                raise ValueError(
                    f'Invalid strategy for battle wait event {event_name}: '
                    f'{strategy_name!r}'
                )

            function_names.append(f'_bw_{event_name}_{strategy_name}')
        return function_names

    def override(self, *arg, **kwargs):
        if kwargs:
            raise TypeError(
                'sequence is not supported' if 'sequence' in kwargs else f'Unexpected keyword arguments: {tuple(kwargs)}')
        if not arg:
            return self

        events = [event for event in self.sequence.split('>') if event]
        if 'idle' not in events:
            raise ValueError(f'Sequence {self.sequence!r} must contain "idle"')
        idle_index = events.index('idle')

        for event_strategy in arg:
            if not isinstance(event_strategy, str):
                raise TypeError(f'event_strategy must be a string, got {event_strategy!r}')

            event, separator, strategy = event_strategy.partition('_')
            if not separator or not event or not strategy:
                raise ValueError(f'Invalid event_strategy: {event_strategy!r}')
            if event == 'sequence':
                raise ValueError('sequence cannot be overridden')

            is_new = not hasattr(self, event)
            setattr(self, event, strategy)
            if is_new:
                events.insert(idle_index, event)
                idle_index += 1

        self.sequence = '>'.join(events)
        return self

class battle_wait_strategy:
    """
    用法（入参为 'event_strategy' 字符串或 event=strategy 的 kwargs）:
    1) 装饰器 = 永久覆盖（任务级）:
         @battle_wait_strategy(success='activity')
         def battle_wait(self, *args, **kwargs):
             return self.battle_wait_with_strategy(*args, **kwargs)
    2) with = 临时覆盖（本次调用, 退出还原）:
         with battle_wait_strategy(success='activity'):
             task.battle_wait()
    3) 调用时动态传参（临时更新, 不覆盖, 兼容旧接口）:
         task.battle_wait(random_click_swipt_enable=True)

    新增事件需实现对应 _bw_<event>_<strategy> 的 hook；自定义顺序用 sequence 参数,
    未指定时新增事件插到 failure 与 idle 之间。
    """
    battle_wait_plan: BattleWaitPlan = None

    def __init__(self, *arg, **kwargs):
        self._scope = 'decorator'
        self._battle_wait_plan = BattleWaitPlan(*arg, **kwargs)

    def __enter__(self):
        self._scope = 'temporary'
        self._previous_plan = battle_wait_strategy.battle_wait_plan
        battle_wait_strategy.battle_wait_plan = self._battle_wait_plan
        return self

    def __exit__(self, *exc):
        battle_wait_strategy.battle_wait_plan = self._previous_plan
        return False

    def __str__(self):
        plan = getattr(self, '_battle_wait_plan', None)
        scope = getattr(self, '_scope', 'decorator')
        active_plan = battle_wait_strategy.battle_wait_plan
        return (
            f'{type(self).__name__}('
            f'scope={scope}, '
            f'plan=\n{plan}, '
            f'active_plan=\n{active_plan}'
            f')'
        )

    def __repr__(self):
        return self.__str__()


    def _recreate_cm(self):
        return self

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        # 跨任务重置配置和策略，但是不重置状态
        battle_wait_strategy.battle_wait_plan = self._battle_wait_plan

        @wraps(func)
        def inner(owner, *args: P.args, **kwargs: P.kwargs) -> T:
            # 兼容性处理
            #-----------------------------------------------------------------------
            if kwargs:
                override_kwargs = {}
                override_args = list()
                for key, value in kwargs.items():
                    if key == 'random_click_swipt_enable' and value:
                        override_kwargs['randomclick'] = 'default'
                        override_args.append('randomclick_default')
                current_plan = copy.deepcopy(battle_wait_strategy.battle_wait_plan)
                current_plan = current_plan.override(*override_args)
            else:
                current_plan = battle_wait_strategy.battle_wait_plan
            # -----------------------------------------------------------------------
            # kwargs.setdefault(
            #     'battle_wait_plan',
            #     self.battle_wait_plan,
            # )
            options = battle_wait_options.options or None
            runtime.reset_per_battle()
            runtime.update_options(options, plan=current_plan)
            return func(owner, battle_wait_plan=current_plan, options=options) \
                if options else func(owner, battle_wait_plan=current_plan)

        return inner


class battle_wait_options:
    """
    用法（输入为按 hook 名的 kwargs, 每个值必须是 dict[str, dict]）:
    1) 装饰器 = 永久覆盖（任务级）:
         @battle_wait_options(success={'excludes': [...]})  # 参数
         @battle_wait_strategy(success='activity')   # 策略, 只管 hook 与顺序
         def battle_wait(self, *args, **kwargs):
             return self.battle_wait_with_strategy(*args, **kwargs)
    2) with = 临时覆盖（本次调用, 退出还原）:
         with battle_wait_options(failure={'excludes': [...]}):
             task.battle_wait()
    """
    options: dict = {event: cls() for event, cls in _OPTION_CLASSES.items()}

    def __init__(self, *arg, **kwargs):
        self._scope = 'decorator'
        self._overrides = _options_to_instances(dict(kwargs))

    def __enter__(self):
        self._scope = 'temporary'
        self._prev = type(self).options
        merged = deepcopy(self._prev) or {}
        merged.update(self._overrides)
        type(self).options = merged
        return self

    def __exit__(self, *exc):
        type(self).options = self._prev
        return False

    def __str__(self):
        scope = getattr(self, '_scope', 'decorator')
        return (
            f'{type(self).__name__}('
            f'scope={scope}, '
            f'overrides={self._overrides}, '
            f'options={battle_wait_options.options or {}}'
            f')'
        )
    def __repr__(self):
        return self.__str__()

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        # 装饰器 = 永久覆盖（任务级）; 调用结束后还原，避免跨任务污染
        self._options_saved = type(self).options

        @wraps(func)
        def inner(owner, *args: P.args, **kwargs: P.kwargs) -> T:
            type(self).options = deepcopy(self._overrides)
            try:
                return func(owner, *args, **kwargs)
            finally:
                type(self).options = self._options_saved

        return inner


@dataclass
class PublicContext:
    cross: dict = field(default_factory=dict)
    per_task: PerTaskState = field(default_factory=PerTaskState)
    per_battle: PerBattleState = field(default_factory=PerBattleState)
    options: dict = field(default_factory=dict)  # 所有hook的options

@dataclass
class PrivateContext:
    cross: dict = field(default_factory=dict)
    per_task: dict = field(default_factory=dict)
    per_battle: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)   # 单个hook的options


class runtime:

    task_owner = None
    pri_ctx: dict[str, PrivateContext] = {}
    pub_ctx: PublicContext = None

    def __init__(self, func: Callable):
        self.func = func
        self.hook_name = func.__name__
        update_wrapper(self, func)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        runtime._ensure_pub_default()
        runtime._ensure_pri_default(self.hook_name)

        @wraps(self.func)
        def bound(*args, **kwargs):
            return self(obj, *args, **kwargs)
        return bound

    def __call__(self, owner, *args, **kwargs):
        # 新任务重置一下
        if runtime.task_owner is None or owner is not runtime.task_owner:
            runtime.task_owner = owner
            runtime.reset_per_task()
        runtime._ensure_pub_default()
        runtime._ensure_pri_default(self.hook_name)

        return self.func(owner, pub=runtime.pub_ctx, pri=runtime.pri_ctx[self.hook_name])

    def __str__(self):
        pub = runtime.pub_ctx or PublicContext()
        pri = runtime.pri_ctx.get(self.hook_name) or PrivateContext()

        def _keys(d):
            if isinstance(d, dict):
                return ','.join(d.keys()) or '-'
            if isinstance(d, tuple(_OPTION_CLASSES.values())) or isinstance(d, tuple(_PER_TASK_CLASSES.values())) or isinstance(d, tuple(_PER_BATTLE_CLASSES.values())) or isinstance(d, (PerTaskState, PerBattleState)):
                return ','.join(d.__dataclass_fields__) or '-'
            return str(d)

        return (
            f'runtime({self.hook_name}) '
            f'pub[c:{_keys(pub.cross)},t:{_keys(pub.per_task)},b:{_keys(pub.per_battle)},o:{_keys(pub.options)}] '
            f'pri[c:{_keys(pri.cross)},t:{_keys(pri.per_task)},b:{_keys(pri.per_battle)},o:{_keys(pri.options)}]'
        )

    def __repr__(self):
        return self.__str__()

    @classmethod
    def reset_per_task(cls):
        cls._ensure_pub_default()
        cls.pub_ctx.per_task = PerTaskState()
        for hook_name, ctx in cls.pri_ctx.items():
            event = cls.hook2event(hook_name)
            cls_type = _PER_TASK_CLASSES.get(event, dict)
            ctx.per_task = cls_type()

    @classmethod
    def reset_per_battle(cls):
        cls._ensure_pub_default()
        cls.pub_ctx.per_battle = PerBattleState()
        for hook_name, ctx in cls.pri_ctx.items():
            event = cls.hook2event(hook_name)
            cls_type = _PER_BATTLE_CLASSES.get(event, dict)
            ctx.per_battle = cls_type()

    @classmethod
    def _ensure_pub_default(cls):
        if cls.pub_ctx is None:
            cls.pub_ctx = PublicContext()

    @classmethod
    def _ensure_pri_default(cls, name):
        if name not in cls.pri_ctx:
            event = cls.hook2event(name)
            cls.pri_ctx[name] = PrivateContext(
                per_task=_PER_TASK_CLASSES.get(event, dict)(),
                per_battle=_PER_BATTLE_CLASSES.get(event, dict)(),
            )

    @classmethod
    def hook2event(cls, func_name: str) -> str:
        # '_bw_success_soul'    -> 'success'（strategy 名里带下划线也能正确切出事件名）
        return func_name[len('_bw_'):].rsplit('_', 1)[0]

    @classmethod
    def event2hook(cls, event_name: str, strategy_name: str) -> str:
        return f'_bw_{event_name}_{strategy_name}'

    @classmethod
    def update_options(cls, options: dict[str, object] | None, plan: BattleWaitPlan):
        """
        输入 options = {
                'setup':     OptionSetupDefault(excludes=None),
                'completion': OptionCompletionDefault(),
                'prepare':   OptionPrepareDefault(lock_team=True),
                'preset':    OptionPresetDefault(preset_enable=True, preset_group=1, preset_team=2),
                'success':   OptionSuccessDefault(),                  # 没传字段 → 全默认
                ... # 其余 event 都有
                }

        设置值, 这里key没有直接使用 event 而是 _bw_event_strategy 是因为可能这场战斗和下一场战斗的options不同，需要区分开来
        cls.pub_ctx.options = options  // 直接的一个引用
        runtime.pri_ctx['_bw_prepare_default'].options == OptionPrepareDefault(lock_team=True)
        runtime.pri_ctx['_bw_preset_default'].options  == OptionPresetDefault(preset_enable=True, preset_group=1, preset_team=2)
        runtime.pri_ctx['_bw_success_default'].options == OptionSuccessDefault()
        """
        cls._ensure_pub_default()
        if not isinstance(options, dict):
            raise
        cls.pub_ctx.options = options
        if plan is not None:
            for hook in [plan.function_setup_name] + plan.sequence_function_names():
                cls._ensure_pri_default(hook)
                opt = options.get(cls.hook2event(hook))
                ctx = cls.pri_ctx[hook]
                ctx.options = opt if isinstance(opt, cls._option_class(hook)) \
                    else cls._option_class(hook)()

    @classmethod
    def _option_class(cls, hook_name: str) -> type:
        return _OPTION_CLASSES.get(cls.hook2event(hook_name)) or dict

    @classmethod
    def hook_enabled(cls) -> set:
        _hook_enabled = cls.pub_ctx.per_battle.hook_enabled
        if not _hook_enabled:
            raise
        return _hook_enabled

    @classmethod
    def hook_enabled_update(cls, enable: tuple[str, ...], disable: tuple[str, ...]) -> HookSignal:
        """
        hook_enabled 的更新只能在 BattleWait 上。不可以在 battle_wait_options 或者 battle_wait_strategy 上
        """
        if enable:
            cls.pub_ctx.per_battle.hook_enabled.update(enable)
        if disable:
            cls.pub_ctx.per_battle.hook_enabled.difference_update(disable)
        return HookSignal.CONTINUE


def randomclick_gate(func: Callable) -> Callable:
    """
    randomclick 专属拦截装饰器，零自身状态。全部状态读写透传进来的 pri：
      - per_battle(PerBattleRandomclick): 开场 delay/上限/次数，每场重置
      - per_task (PerTaskRandomclick):   cooldown 上次尝试时刻，跨战斗
    四道门全过才放行 func 真正执行随机动作。
    """
    @wraps(func)
    def wrapper(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        options = pub.options.get('randomclick')
        state_battle = pri.per_battle
        state_task = pri.per_task
        if not isinstance(options, OptionRandomclickDefault):
            raise TypeError(f"randomclick options must be OptionRandomclickDefault, got {type(options)!r}")
        if not isinstance(state_battle, PerBattleRandomclick):
            raise TypeError(f"randomclick per_battle state must be PerBattleRandomclick, got {type(state_battle)!r}")
        if not isinstance(state_task, PerTaskRandomclick):
            raise TypeError(f"randomclick per_task state must be PerTaskRandomclick, got {type(state_task)!r}")
        if not self.is_in_battle(is_screenshot=False):
            return HookSignal.CONTINUE

        now = time.time()

        # 第一次调用：解析 start_delay 和 execution_limit（只解析一次）
        if state_battle.first_allowed_time == 0.0:
            state_battle.start_delay_resolved = random.uniform(*options.start_delay)
            state_battle.execution_limit_resolved = random.randint(*options.execution_limit)
            state_battle.first_allowed_time = now + state_battle.start_delay_resolved
            return HookSignal.CONTINUE

        # Gate 1: start_delay 未到
        if now < state_battle.first_allowed_time:
            return HookSignal.CONTINUE

        # Gate 2: execution_limit 已满
        if state_battle.execution_count >= state_battle.execution_limit_resolved:
            return HookSignal.CONTINUE

        # Gate 3: cooldown 未到（记在 per_task 跨战斗，秒掉的小战斗也能续上间隔）
        if now - state_task.last_attempt_time < random.uniform(*options.cooldown):
            return HookSignal.CONTINUE

        # 记录本次尝试时间（无论概率是否通过，都算一次 cooldown 周期）
        state_task.last_attempt_time = now

        # Gate 4: trigger_probability 概率判定
        if random.random() >= options.trigger_probability:
            return HookSignal.CONTINUE

        # 通过全部四道门，放行真正执行随机动作
        state_battle.execution_count += 1
        return func(self, pub, pri)

    return wrapper


class BattleWait(BaseTask, GeneralBattleAssets):

    def __new__(cls, *args, **kwargs):
        for klass in reversed(cls.__mro__):
            # 找遍整个继承链，从父到子
            if klass is object:
                continue
            if klass.__dict__.get('_runtime_auto_decorated'):
                continue
            klass._runtime_auto_decorated = True
            for name, attr in list(vars(klass).items()):
                if name.startswith('_bw_') and callable(attr) and not isinstance(attr, runtime):
                    setattr(klass, name, runtime(attr))
        return super().__new__(cls)

    # ----------------------------------------------------------------------------------------------------------------
    # loadout：一行一个 event（event + strategy + options），全量快照，默认值来源 battle_wait.py，不裸写：
    #   strategies: dict[event -> strategy]，有序，key 是 hook 名，支持 prepare='default' 这类逐 hook 设置
    #   options:    dict[event -> Option 实例]，全部字段可见
    # 跑法：
    #   with battle_wait_strategy(**strategies), battle_wait_options(**options):
    #       self.battle_wait()
    # ----------------------------------------------------------------------------------------------------------------
    @classmethod
    def loadout_default(cls) -> tuple[dict, dict]:
        """
        默认策略 + 默认 options 的全量快照（不是 diff，是完整的）。
          策略来源 BattleWaitPlan()（battle_wait.py），按 sequence 顺序展开成 dict；
          options 来源 battle_wait_options.options（battle_wait.py）。
        """
        plan = BattleWaitPlan()
        strategies = {e: getattr(plan, e) for e in plan.sequence.replace(' ', '').split('>') if e}
        options = deepcopy(battle_wait_options.options) or {}
        return strategies, options

    @classmethod
    def loadout_show(cls, loadout: tuple[dict, dict] | None = None) -> None:
        """
        输出类似：
        event       strategy    options
        idle        default     OptionIdleDefault()
        prepare     default     OptionPrepareDefault(lock_team=False)
        preset      default     OptionPresetDefault(preset_enable=False, preset_group=1, preset_team=1)
        green       default     OptionGreenDefault(green_enable=False, green_mark=<GreenMarkType.GREEN_LEFT1: 'green_left1'>)
        """
        strategies, options = loadout if loadout is not None else cls.loadout_default()
        order = []
        seen = set()
        for event in options:
            order.append(event)
            seen.add(event)
        for event in strategies:
            if event not in seen:
                order.append(event)
        print('=' * 64)
        print(f'{"event":<12}{"strategy":<12}options')
        for event in order:
            print(f'{event:<12}{strategies.get(event, "default"):<12}{options.get(event)!r}')
        print('=' * 64)

    @classmethod
    def state_show(cls) -> None:
        """
        输出类似：
        event       strategy    enabled   per_task | per_battle
        completion  default     True      {} | {}
        idle        default     True      {} | {}
        prepare     default     False     {} | {'done': True}
        ----------------------------------------------------------------
        pub         per_task    count 等全局跨任务状态
        pub         per_battle  success / hook_enabled 等全局跨战斗状态
        """
        runtime._ensure_pub_default()
        enabled = runtime.hook_enabled()

        def _nondefault(o):
            if isinstance(o, dict):
                return dict(o)
            return {f.name: getattr(o, f.name) for f in fields(o) if getattr(o, f.name) != f.default}

        options = cls.loadout_default()[1]
        order = list(options)
        hooks = sorted(
            runtime.pri_ctx,
            key=lambda h: order.index(runtime.hook2event(h)) if runtime.hook2event(h) in order else len(order),
        )
        print('=' * 64)
        print(f'{"event":<12}{"strategy":<12}{"enabled":<10}per_task | per_battle')
        for hook in hooks:
            event = runtime.hook2event(hook)
            strategy = hook[len(f'_bw_{event}_'):]
            ctx = runtime.pri_ctx[hook]
            print(f'{event:<12}{strategy:<12}{str(event in enabled):<10}'
                  f'{_nondefault(ctx.per_task)} | {_nondefault(ctx.per_battle)}')
        print('-' * 64)
        pub = runtime.pub_ctx
        print(f'{"pub":<12}{"":<12}{"per_task":<10}{_nondefault(pub.per_task)}')
        print(f'{"pub":<12}{"":<12}{"per_battle":<10}{_nondefault(pub.per_battle)}')
        print('=' * 64)
        time.sleep(0.6)

    # ------------------------------------------------------------------------------------------------------------------
    # build in
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_setup_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info('Start battle process')
        return HookSignal.DONE

    def _bw_completion_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        logger.info('Battle completion process')
        state = pri.per_battle
        options = pri.options
        if not isinstance(state, PerBattleCompletion) or not isinstance(options, OptionCompletionDefault):
            raise
        if options.check_imgs is None:
            pub.per_task.count += 1
            # self.current_count += 1  # 兼容旧的计数
            return HookSignal.DONE
        # 如果需要进一步确认
        if not isinstance(options.check_imgs, list):
            raise
        appears = [self.appear(check) for check in options.check_imgs]
        if any(appears):
            pub.per_task.count += 1
            # self.current_count += 1  # 兼容旧的计数
            return HookSignal.DONE
        # check_imgs 全没出现 → 兜底点击回退界面：进入 completion 满 8s 才首次点击，之后每 8s 一次
        if state.fallback_timer is None:
            state.fallback_timer = Timer(8).start()
        if not isinstance(state.fallback_timer, Timer):
            raise
        if not state.fallback_timer.reached():
            return HookSignal.CONTINUE
        state.fallback_timer.reset()
        if state.click_stage_2 is None:
            state.click_stage_2 = PerBattleSuccess.reward_exclude_click(self, options.excludes, name='completion_exclude_click')
        x, y = state.click_stage_2.coord()
        self.device.click(x=x, y=y, control_name='completion_exclude_click')
        return HookSignal.CONTINUE

    def _bw_interrupt_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        # 比如 御魂溢出
        return HookSignal.CONTINUE

    def _bw_success_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        state = pri.per_battle
        options = pri.options
        if not isinstance(state, PerBattleSuccess) or not isinstance(options, OptionSuccessDefault):
            raise
        if state.click_stage_1 is None:
            state.click_stage_1 = PerBattleSuccess.reward_exclude_click(self, pri.options.excludes_1, name='reward_exclude_click_1')
        if state.click_stage_2 is None:
            state.click_stage_2 = PerBattleSuccess.reward_exclude_click(self, pri.options.excludes_2, name='reward_exclude_click_2')

        if self.appear_then_click(self.I_WIN, interval=0.8):
            self.click(state.click_stage_1)
            return HookSignal.CONTINUE
        appear_ghost, appear_reward, appear_gold, appear_skin = (
            self.appear(self.I_GREED_GHOST),
            self.appear(self.I_REWARD),
            self.appear(self.I_REWARD_GOLD),
            self.appear(self.I_REWARD_GOLD_SNAKE_SKIN)
        )
        if not any([appear_ghost, appear_reward, appear_gold, appear_skin]):
            return HookSignal.CONTINUE
        logger.info('Win battle')
        timer = Timer(20).start()
        while 1:
            self.screenshot()

            # 不小心点到了具体的奖励，他会弹出这个物品的详细描述 里面必定包含有“获取途径”
            if self.appear(self.I_END_FIX_1) or self.appear(self.I_END_FIX_2):
                self.click(self.C_REWARD_2, interval=1.5)

            _appear_ghost, _appear_reward, _appear_gold, _appear_skin = (
                self.appear(self.I_GREED_GHOST, threshold=0.6),
                self.appear(self.I_REWARD),
                self.appear(self.I_REWARD_GOLD),
                self.appear(self.I_REWARD_GOLD_SNAKE_SKIN)
            )
            # logger.info(f'_appear_ghost: {_appear_ghost} _appear_reward: {_appear_reward} _appear_gold: {_appear_gold} _appear_skin: {_appear_skin}')
            if any([_appear_ghost, _appear_reward, _appear_gold, _appear_skin]):
                if random.random() < 0.02:
                    # 有一定的概率专门点击具体的奖励物品
                    x, y = state.click_stage_2.coord_in_excluded(None)
                    self.device.click(x=x, y=y, control_name='reward_item')
                    continue
                self.click(state.click_stage_2, interval=1.5)
            else:
                logger.info('Get all reward')
                pub.per_battle.success = BattleResult.SUCCESS
                return runtime.hook_enabled_update(
                    enable=('completion',),
                    disable=tuple(['success', 'failure']),
                )
            if timer.reached_and_reset():
                logger.warning('battle')
                break
        return HookSignal.CONTINUE

    def _bw_failure_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        if self.appear(self.I_FALSE, threshold=0.8):
            logger.warning('False battle')
            self.ui_click_until_disappear(self.I_FALSE)
            pub.per_battle.success = BattleResult.FAILURE
            return runtime.hook_enabled_update(
                enable=('completion', ),
                disable=tuple(['success', 'failure']),
            )
        return HookSignal.CONTINUE

    def _bw_idle_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        return HookSignal.CONTINUE

    def _bw_prepare_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        pri_options = pri.options if isinstance(pri.options, OptionPrepareDefault) else None
        state = pri.per_battle if isinstance(pri.per_battle, PerBattlePrepare) else None
        if pri_options is None or state is None:
            return HookSignal.CONTINUE
        if state.done:
            return HookSignal.CONTINUE
        # 如果是锁队伍的，就直接跳过, 开启后面的 绿标，红标，应声虫
        # 如果确定进入正式战斗中了 也是同样的操作
        if pri_options.lock_team or self.is_in_real_battle(False):
            logger.info('Prepare stage finish')
            state.done = True
            return runtime.hook_enabled_update(
                enable=('green', 'red', 'echo'),
                disable=('prepare', 'preset'),
            )
        # 如果开启了切阵容，就等执行切阵容完成(切阵容操作会自动把准备按钮给按消失), 这里会等8秒钟，时间一到自动关闭准备阶段
        # 切阵容按 per_task 是一次性的：本任务已切过（done）就不再开定时器等，直接按准备开打
        preset_done = next((
            ctx.per_task.done
            for hook, ctx in runtime.pri_ctx.items()
            if runtime.hook2event(hook) == 'preset' and isinstance(ctx.per_task, PerTaskPreset)
        ), False)
        if pub.options.get('preset', OptionPresetDefault).preset_enable and not preset_done:
            if state.timer is None:
                state.timer = Timer(6).start()
                # return HookSignal.CONTINUE
                return runtime.hook_enabled_update(
                    enable=('preset',),
                    disable=(),
                )
            # 时间没到就一直等吧
            if not state.timer.reached():
                return HookSignal.CONTINUE
            # 计时8秒时间到了， 那就一直按 准备按钮 直到消失去
            # 不要把这行代码合并到下面去
            self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=0.8)
            return HookSignal.CONTINUE

        # 没有切阵容那就一直按 准备按钮 直到消失去]

        self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1)
        return HookSignal.CONTINUE

    def _bw_preset_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        切阵容：切换预设队伍，每个任务只执行一次
        """
        pri_options = pri.options if isinstance(pri.options, OptionPresetDefault) else None
        state = pri.per_task if isinstance(pri.per_task, PerTaskPreset) else None
        if pri_options is None or state is None:
            return HookSignal.CONTINUE
        if not pri_options.preset_enable or state.done:
            return HookSignal.CONTINUE

        logger.info("Preset is enable")
        # 点击预设按钮
        while 1:
            self.screenshot()
            if self.appear(self.I_PRESET_ENSURE):
                break
            # 首个队伍没有满足5个式神，未出现预设按钮的情况下跳出循环
            if self.appear(self.I_PRESENT_LESS_THAN_5):
                break
            if self.appear_then_click(self.I_PRESET, threshold=0.8, interval=1):
                continue
            if self.appear_then_click(self.I_PRESET_WIT_NUMBER, threshold=0.8, interval=1):
                continue
            if self.ocr_appear(self.O_PRESET):
                self.click(self.O_PRESET, interval=1)
                continue
            if self.ocr_appear(self.O_PRESET_FULL):
                self.click(self.O_PRESET_FULL, interval=1)
                continue
        logger.info("Click preset button")

        def get_unselect_color(tmp1, tmp2, tmp3, size):
            # 获取未选择分组的颜色，3组之中必定存在两个颜色相似
            color_1 = get_color(self.device.image,
                                (tmp1.roi_back[0], tmp1.roi_back[1],
                                 tmp1.roi_back[0] + size[0], tmp1.roi_back[1] + size[1]))
            color_2 = get_color(self.device.image,
                                (tmp2.roi_back[0], tmp2.roi_back[1],
                                 tmp2.roi_back[0] + size[0], tmp2.roi_back[1] + size[1]))
            color_3 = get_color(self.device.image,
                                (tmp3.roi_back[0], tmp3.roi_back[1],
                                 tmp3.roi_back[0] + size[0], tmp3.roi_back[1] + size[1]))
            if color_similar(color_1, color_2):
                return color_1
            if color_similar(color_2, color_3):
                return color_2
            return color_3

        # 选择预设组
        tmp = self.__getattribute__("C_PRESET_GROUP_" + str(pri_options.preset_group))
        if tmp is None:
            tmp = self.C_PRESET_GROUP_1
        color_size = [self.C_PRESET_GROUP_1.roi_back[2],
                      self.C_PRESET_GROUP_1.roi_back[3]]
        unselected_color = (224.9, 208.3, 187.4)
        while True:
            self.screenshot()
            color_tmp = get_color(self.device.image,
                                  (tmp.roi_back[0], tmp.roi_back[1], tmp.roi_back[0] + color_size[0],
                                   tmp.roi_back[1] + color_size[1]))
            if color_similar(color_tmp, unselected_color):
                self.click(tmp, interval=0.2)
                continue
            break
        logger.info("Select preset group")

        # 选择预设的队伍
        time.sleep(0.5)
        tmp = self.__getattribute__("C_PRESET_TEAM_" + str(pri_options.preset_team))
        if tmp is None:
            tmp = self.C_PRESET_TEAM_1
        color_size = [5, 5]
        unselected_color = (216.8, 185.0, 146.8)
        while True:
            self.screenshot()
            color_tmp = get_color(self.device.image,
                                  (tmp.roi_back[0], tmp.roi_back[1], tmp.roi_back[0] + color_size[0],
                                   tmp.roi_back[1] + color_size[1]))
            if color_similar(color_tmp, unselected_color):
                self.click(tmp, interval=0.2)
                continue
            break
        self.click(tmp)
        logger.info("Select preset team")

        # 点击预设确认
        self.wait_until_appear(self.I_PRESET_ENSURE, wait_time=1)
        click_timer = Timer(4).start()
        while 1:
            self.screenshot()
            if click_timer.reached():
                logger.warning("Switch preset failure")
            if not self.appear(self.I_PRESET_ENSURE):
                break
            if self.appear_then_click(self.I_PRESET_ENSURE, threshold=0.8, interval=1):
                continue
        logger.info("Click preset ensure")
        state.done = True
        return runtime.hook_enabled_update(
            enable=(),
            disable=('preset',),
        )

    def _bw_green_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        绿标：标记己方式神，每场战斗只执行一次
        """
        pri_options = pri.options if isinstance(pri.options, OptionGreenDefault) else None
        state = pri.per_battle if isinstance(pri.per_battle, PerBattleGreen) else None
        if pri_options is None or state is None:
            return HookSignal.CONTINUE
        if not pri_options.green_enable or state.done:
            return runtime.hook_enabled_update(
                enable=(),
                disable=('green',),
            )

        logger.info("Green is enable")
        x, y = None, None
        match pri_options.green_mark:
            case GreenMarkType.GREEN_LEFT1:
                x, y = self.C_GREEN_LEFT_1.coord()
                logger.info("Green left 1")
            case GreenMarkType.GREEN_LEFT2:
                x, y = self.C_GREEN_LEFT_2.coord()
                logger.info("Green left 2")
            case GreenMarkType.GREEN_LEFT3:
                x, y = self.C_GREEN_LEFT_3.coord()
                logger.info("Green left 3")
            case GreenMarkType.GREEN_LEFT4:
                x, y = self.C_GREEN_LEFT_4.coord()
                logger.info("Green left 4")
            case GreenMarkType.GREEN_LEFT5:
                x, y = self.C_GREEN_LEFT_5.coord()
                logger.info("Green left 5")
            case GreenMarkType.GREEN_MAIN:
                x, y = self.C_GREEN_MAIN.coord()
                logger.info("Green main")

        # 等待那个准备的消失
        while 1:
            self.screenshot()
            if not self.appear(self.I_PREPARE_HIGHLIGHT):
                break

        # 判断有无坐标的偏移
        self.appear_then_click(self.I_LOCAL)
        time.sleep(0.3)
        # 点击绿标
        self.device.click(x, y)
        state.done = True
        return runtime.hook_enabled_update(
            enable=(),
            disable=('green',),
        )

    def _bw_red_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        红标：点击对手的式神，暂为空壳
        """
        state = pri.per_battle

        state.done = True
        return runtime.hook_enabled_update(
            enable=(),
            disable=('red',),
        )

    def _bw_echo_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        应声虫：战斗中进入聊天界面复制粘贴，暂为空壳
        """
        state = pri.per_battle

        state.done = True
        return runtime.hook_enabled_update(
            enable=(),
            disable=('echo',),
        )

    @randomclick_gate
    def _bw_randomclick_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        match random.randint(0, 2):
            case 0:
                self.click(self.C_RANDOM_CLICK, interval=20)
            case 1:
                self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
            case 2:
                self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
        return HookSignal.CONTINUE

    # custom
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_success_soul(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        state = pri.per_battle
        options = pri.options
        if not isinstance(state, PerBattleSuccess) or not isinstance(options, OptionSuccessDefault):
            raise TypeError("battle wait option 'success' must be an OptionSuccessDefault")
        if state.click_stage_1 is None:
            state.click_stage_1 = PerBattleSuccess.reward_exclude_click(self, options.excludes_1, name='success_exclude_click')
        action_click = state.click_stage_1
        if self.appear_then_click(self.I_WIN, interval=0.8):
            return HookSignal.CONTINUE
        appear_ghost, appear_reward, appear_gold, appear_skin = (
            self.appear(self.I_GREED_GHOST),
            self.appear(self.I_REWARD),
            self.appear(self.I_REWARD_GOLD),
            self.appear(self.I_REWARD_GOLD_SNAKE_SKIN)
        )
        if not any([appear_ghost, appear_reward, appear_gold, appear_skin]):
            return HookSignal.CONTINUE
        logger.info('Win battle')
        timer = Timer(20).start()
        while 1:
            self.screenshot()

            _appear_ghost, _appear_reward, _appear_gold, _appear_skin = (
                self.appear(self.I_GREED_GHOST, threshold=0.6),
                self.appear(self.I_REWARD),
                self.appear(self.I_REWARD_GOLD),
                self.appear(self.I_REWARD_GOLD_SNAKE_SKIN)
            )
            # logger.info(f'_appear_ghost: {_appear_ghost} _appear_reward: {_appear_reward} _appear_gold: {_appear_gold} _appear_skin: {_appear_skin}')
            if any([_appear_ghost, _appear_reward, _appear_gold, _appear_skin]):
                self.click(action_click, interval=1.5)
            else:
                logger.info('Get all reward')
                pub.per_battle.success = BattleResult.SUCCESS
                return runtime.hook_enabled_update(
                    enable=('completion',),
                    disable=tuple(['success', 'failure']),
                )
            if timer.reached_and_reset():
                logger.warning('battle ')
                break
        return HookSignal.CONTINUE

    @cached_property
    def exclude_click_activity(self, areas: list[str] = None) -> RuleClickExclude:
        inputs = []
        for area in ['C_END_MESSAGE_RIGHT_TOP', 'C_END_ACTIVITY_REWARD']:
            click = getattr(self, area, None)
            if click is None:
                raise ValueError(f'Unknown success exclusion click: {area!r}')
            inputs.append(click)
        return RuleClickExclude(inputs, name='exclude_click_activity', strategy='rejection', distribution='uniform')

    def _bw_success_activity(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        战斗结算是有 “获得奖励” 的适用
        """
        if not self.appear(self.I_UI_REWARD):
            return HookSignal.CONTINUE
        self.screenshot()
        if not self.appear(self.I_UI_REWARD):
            return HookSignal.CONTINUE

        logger.info('Win battle')
        timer = Timer(20).start()
        while 1:
            self.screenshot()

            # 不小心点到了具体的奖励，他会弹出这个物品的详细描述 里面必定包含有“获取途径”
            if self.appear(self.I_END_FIX_1) or self.appear(self.I_END_FIX_2) or self.appear(self.I_END_FIX_3):
                self.screenshot()
                if self.appear(self.I_END_FIX_1) or self.appear(self.I_END_FIX_2) or self.appear(self.I_END_FIX_3):
                    self.click(self.C_REWARD_2, interval=2.5)
                continue

            if self.appear(self.I_UI_REWARD):
                if random.random() < 0.02:
                    # 有一定的概率专门点击具体的奖励物品
                    x, y = self.exclude_click_activity.coord_in_excluded(['C_END_ACTIVITY_REWARD'])
                    self.device.click(x=x, y=y, control_name='reward_item')
                    continue
                self.click(self.exclude_click_activity, interval=2.5)
            elif not self.appear(self.I_END_FIX_2):
                self.screenshot()
                if any([self.appear(self.I_UI_REWARD), self.appear(self.I_END_FIX_1), self.appear(self.I_END_FIX_2), self.appear(self.I_END_FIX_3)]):
                    continue
                logger.info('Get all reward')
                pub.per_battle.success = BattleResult.SUCCESS
                return runtime.hook_enabled_update(
                    enable=('completion', ),
                    disable=tuple(['success', 'failure']),
                )

            if timer.reached_and_reset():
                logger.warning('battle ')
                break
        return HookSignal.CONTINUE


    # ------------------------------------------------------------------------------------------------------------------
    def battle_wait_with_strategy(self, *args, **kwargs) -> bool:
        """
        理解 event + strategy 概念： 把战斗过程抽象为一系列触发事件以及对应的实现函数，也称hook。
        event + strategy 拼成了一个hook, 一个 event 在一次战斗过程中只能挂载一个 strategy
        默认定义的 hook 有 BattleWaitPlan.HOOKS_DEFAULT = ('setup', 'completion', 'interrupt', 'success', 'failure', 'idle', 'prepare', 'preset', 'green', 'red', 'echo')  如果你填的没有，会使用默认的补全去的
        这些 hook 跑在一个 while 里面，默认的调用顺序 BattleWaitPlan.SEQUENCE_DEFAULT = 'completion > interrupt > prepare > preset > green > red > echo > success > failure > idle'
        setup 没有跑在 while里面 而是在 while之前， 比如一个战斗过程可以表示为:
        setup_default()
        while 1:
            completion_default()
            interrupt_default()
            success_default()
            failure_default()
            idle_default()
        围绕hook从两个维度来构建一个战斗系统， options 表示每一个hook的配置选项， public 和 private 表示每一个hook的共享和私有状态。分别有两个生命周期
        | 自定义 /生命周期 | 跨任务 | 任务共享               | 单次战斗       |
        | ------------- | ----- | --------------------- | ------------ |
        |   strategy    | 不做   | @battle_wait_strategy | with 上下文   |
        |   options     | 不做   | @battle_wait_options  | with 上下文   |
        |   public      | cross | per_task              | per_battle   |
        |   private     | cross | per_task              | per_battle   |

        三种自定义策略方法见 battle_wait_strategy 的 docstring。
        自定义options方法见 battle_wait_options 的 docstring
        """
        battle_wait_plan = kwargs.get('battle_wait_plan')
        if battle_wait_plan is None:
            battle_wait_plan = BattleWaitPlan()

        setup_func = getattr(self, battle_wait_plan.function_setup_name, self._bw_setup_default)
        setup_func()
        runtime.hook_enabled_update(
            enable=(),
            disable=('setup',),
        )
        handlers = [getattr(self, func_name, None) for func_name in battle_wait_plan.sequence_function_names()]
        self.setup_hook(handlers=handlers)

        while True:
            self.screenshot()
            hook_enabled = runtime.hook_enabled()
            # self.state_show()
            for handler in handlers:
                if runtime.hook2event(handler.__name__) not in hook_enabled:
                    continue
                result = handler()
                if handler.__name__.startswith('_bw_completion') and result == HookSignal.DONE:
                    return runtime.pub_ctx.per_battle.success == BattleResult.SUCCESS
                if result == HookSignal.CONTINUE:
                    continue

    @classmethod
    def setup_hook(cls, handlers: list[Callable]):
        """
        默认的： 'setup', 'completion', 'interrupt', 'prepare', 'preset', 'green', 'red', 'echo', 'success', 'failure', 'idle'
        战斗开始下关闭的 completion, 'preset', 'green', 'red', 'echo'
        检测到进入准备阶段后开启 `preset` 来进入切换阵容，准备阶段结束后开启  'green', 'red', 'echo'

        """
        _hook_enabled = tuple(runtime.hook2event(h.__name__) for h in handlers if h)
        _hook_disabled = ('completion', 'preset', 'green', 'red', 'echo')
        runtime.hook_enabled_update(enable=_hook_enabled, disable=_hook_disabled)




if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.Component.GeneralBattle.general_battle import GeneralBattle
    c = Config('oas1')
    d = Device(c)








