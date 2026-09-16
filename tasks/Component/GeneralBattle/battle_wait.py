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
from copy import deepcopy


from functools import wraps, update_wrapper
from dataclasses import dataclass, field
from typing import TypeVar, ParamSpec, Callable
from enum import Enum, auto
from cached_property import cached_property

from module.logger import logger
from module.base.timer import Timer
from module.atom.click import RuleClickExclude

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets


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
    'setup', 'completion', 'interrupt', 'success', 'failure', 'idle',
)
_SEQUENCE_DEFAULT: str = 'completion > interrupt > success > failure >'

# hook options 默认值（装饰器 @battle_wait_options / with 上下文写入类槽）
_DEFAULT_OPTIONS: dict[str, dict] = {
    'success': {
        'reward_exclude_click_1': [
            'C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1',
            'C_END_BUFF_AREA_2', 'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
        ],
        'reward_exclude_click_2': [
            'C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1',
            'C_END_BUFF_AREA_2', 'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
            'C_END_1_1', 'C_END_1_2', 'C_END_1_3', 'C_END_1_4',
            'C_END_1_5', 'C_END_1_6',
        ],
    },
}

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
            runtime.update_options(options)
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
    _DEFAULT_OPTIONS = _DEFAULT_OPTIONS
    options: dict[str, dict] = deepcopy(_DEFAULT_OPTIONS)

    def __init__(self, *arg, **kwargs):
        self._scope = 'decorator'
        self._overrides = dict(kwargs)

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
        runtime._ensure_pub()
        runtime._ensure_pri(self.hook_name)

        @wraps(self.func)
        def bound(*args, **kwargs):
            return self(obj, *args, **kwargs)
        return bound

    def __call__(self, owner, *args, **kwargs):
        # 新任务重置一下
        if runtime.task_owner is None or owner is not runtime.task_owner:
            runtime.task_owner = owner
            runtime.reset_per_task()
        runtime._ensure_pub()
        runtime._ensure_pri(self.hook_name)

        return self.func(owner, pub=runtime.pub_ctx, pri=runtime.pri_ctx[self.hook_name])

    def __str__(self):
        pub = runtime.pub_ctx or PublicContext()
        pri = runtime.pri_ctx.get(self.hook_name) or PrivateContext()

        def _keys(d):
            if isinstance(d, dict):
                return ','.join(d.keys()) or '-'
            if isinstance(d, (PerTaskState, PerBattleState)):
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
        cls._ensure_pub()
        cls.pub_ctx.per_task = PerTaskState()
        for ctx in cls.pri_ctx.values():
            ctx.per_task = {}

    @classmethod
    def reset_per_battle(cls):
        cls._ensure_pub()
        cls.pub_ctx.per_battle = PerBattleState()
        for ctx in cls.pri_ctx.values():
            ctx.per_battle = {}

    @classmethod
    def _ensure_pub(cls):
        if cls.pub_ctx is None:
            cls.pub_ctx = PublicContext()

    @classmethod
    def _ensure_pri(cls, name):
        if name not in cls.pri_ctx:
            cls.pri_ctx[name] = PrivateContext()

    @classmethod
    def hook2event(cls, func_name: str) -> str:
        # '_bw_success_soul'    -> 'success'（strategy 名里带下划线也能正确切出事件名）
        return func_name[len('_bw_'):].rsplit('_', 1)[0]

    @classmethod
    def update_options(cls, options: dict[str, dict]):
        cls._ensure_pub()
        if not isinstance(options, dict):
            cls.pub_ctx.options = {}
            for ctx in cls.pri_ctx.values():
                ctx.options = {}
            return
        cls.pub_ctx.options = options
        for hook_name, ctx in cls.pri_ctx.items():
            ctx.options = options.get(cls.hook2event(hook_name)) or {}

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
        cls.pub_ctx.per_battle.hook_enabled.update(enable)
        cls.pub_ctx.per_battle.hook_enabled.difference_update(disable)
        return HookSignal.CONTINUE


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

    # ------------------------------------------------------------------------------------------------------------------
    @cached_property
    def exclude_button_stage_1(self):
        return ['C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1', 'C_END_BUFF_AREA_2',
                'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
                ]

    @cached_property
    def exclude_button_stage_2(self):
        return ['C_END_MESSAGE_RIGHT_TOP', 'C_END_BUFF_AREA_1', 'C_END_BUFF_AREA_2', 'C_END_SOUL_RECORD', 'C_END_SOUL_DETAILS',
                'C_END_1_1', 'C_END_1_2', 'C_END_1_3', 'C_END_1_4', 'C_END_1_5', 'C_END_1_6',
                ]

    def reward_exclude_click(self, areas: list[str] = None, name: str = 'success_exclude_click') -> RuleClickExclude:
        inputs = []
        for area in areas:
            click = getattr(self, area, None)
            if click is None:
                raise ValueError(f'Unknown success exclusion click: {area!r}')
            inputs.append(click)
        return RuleClickExclude(inputs, name=name)

    def reward_exclude_click_1(self, areas: list[str] = None) -> RuleClickExclude:
        return self.reward_exclude_click(areas, name='reward_exclude_click_1')

    def reward_exclude_click_2(self, areas: list[str] = None) -> RuleClickExclude:
        return self.reward_exclude_click(areas, name='reward_exclude_click_2')

    # build in
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_setup_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        """
        options: dict = {
            ‘excludes’
        }
        """
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info('Start battle process')

        pri_options = pri.options if isinstance(pri.options, dict) else {}
        success_options = pri_options.get('success') or {}
        if not isinstance(success_options, dict):
            raise TypeError("battle wait option 'success' must be a dict")
        excludes = success_options.get('excludes')
        exclude_stage_1 = excludes if excludes is not None else self.exclude_button_stage_1
        exclude_stage_2 = excludes if excludes is not None else self.exclude_button_stage_2
        self._reward_exclude_click_1 = self.reward_exclude_click_1(exclude_stage_1)
        self._reward_exclude_click_2 = self.reward_exclude_click_2(exclude_stage_2)
        # print(self._reward_exclude_click_1)
        # print(self._reward_exclude_click_2)
        return HookSignal.DONE

    def _bw_completion_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        logger.info('Battle completion process')
        pub.per_task.count += 1
        return HookSignal.DONE

    def _bw_interrupt_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        # 比如 御魂溢出
        return HookSignal.CONTINUE

    def _bw_success_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        if self.appear_then_click(self.I_WIN, interval=0.8):
            self.click(self._reward_exclude_click_1)
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
                    x, y = self._reward_exclude_click_2.coord_in_excluded(None)
                    self.device.click(x=x, y=y, control_name='reward_item')
                    continue
                self.click(self._reward_exclude_click_2, interval=1.5)
            else:
                logger.info('Get all reward')
                pub.success = True
                pub.completion = True
                return HookSignal.CONTINUE
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

    def _bw_randomclick_default(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        return HookSignal.CONTINUE
        done = pri.per_battle.get('_bw_randomclick_state', False)
        if done:
            return HookSignal.CONTINUE
        if not self.is_in_battle(is_screenshot=False):
            return HookSignal.CONTINUE
        if random.random() < 0.005 :  # 低概率
            rand_type = random.randint(0, 2)
            match rand_type:
                case 0:
                    self.click(self.C_RANDOM_CLICK, interval=20)
                case 1:
                    self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
                case 2:
                    self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
            pri.per_battle['_bw_randomclick_state'] = True
            # 重新设置为长战斗
            # self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            time.sleep(0.4)  # 这样的好像不对
        return HookSignal.CONTINUE

    # custom
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_success_soul(self, pub: PublicContext, pri: PrivateContext) -> HookSignal:
        options: dict[str, dict] = pub.options if isinstance(pub.options, dict) else {}
        success_options = options.get('success') or {}
        if not isinstance(success_options, dict):
            raise TypeError("battle wait option 'success' must be a dict")
        action_click = self.reward_exclude_click(success_options.get('excludes'))
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
                pub.success = True
                pub.completion = True
                return HookSignal.CONTINUE
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
        默认定义的 hook 有 BattleWaitPlan.HOOKS_DEFAULT = ('setup', 'completion', 'interrupt', 'success', 'failure', 'idle')
        这些 hook 跑在一个 while 里面，默认的调用顺序 BattleWaitPlan.SEQUENCE_DEFAULT = 'completion > interrupt > success > failure > idle'
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

        ----------------------------------------------------------------------------------------------------------------
        三种自定义策略方法：
        1. 使用装饰器battle_wait_strategy, 将会覆盖掉类变量
            @battle_wait_strategy( 'reserve_default', 'idle_default', failure='default')
            def battle_wait(self, *args, **kwargs):
                return self.battle_wait_with_strategy(*args, **kwargs)
        2. 使用 with 上下文 （！在1基础上）, 将会临时覆盖掉原先的类变量，退出后恢复
            with battle_wait_strategy('reserve_default'):
                test_battle_wait.battle_wait()
        3. 调用时动态传参 （！在1基础上）， 不覆盖，就临时更新策略
            obj.battle_wait(random_click_swipt_enable=1)  # 详细参数看 battle_wait_strategy.__call__()

        自定义hook就是字符串拼起来：  battle_wait_strategy的入参可以有 ‘event_strategy’ 或者 'event=strategy'
        可以添加任意 event 以及其对应的 strategy。比如 ‘yyy_default’ 'abcd_edf'
        但是必须要实现对应的hook 上面的比如 _bw_yyy_default() 以及 _bw_abcd_edf()
        hook 可以自定义顺序，比如 battle_wait_strategy(sequence='completion > interrupt > success > failure > idle')
        如果没有指定sequence， 新增的event会按照传参时候从左到右排序，左边高优先级，新增的会插入到 failure 和 idle 之间

        ----------------------------------------------------------------------------------------------------------------
        如果希望每一个hook带上参数：
        1. 在 battle_wait_strategy 定义了一组默认的 options
        2. 可以在装饰器定义 @battle_wait_strategy(options = options)，这里将会覆盖掉原先的 battle_wait_strategy.options
        3. 上下文带上  with battle_wait_strategy(...).with_options(options)，同样也是临时覆盖掉 battle_wait_strategy.options
        4.
        options: dict[str: dict] = {
            "setup": {...}
            ...
        }
        ----------------------------------------------------------------------------------------------------------------
        跨战斗，考虑把状态挂到方法上，而不是挂到类对象上。】
        我突然感觉 一个类里面装了 策略和参数，这样不好，考虑拆分成两个装饰器

        """
        battle_wait_plan = kwargs.get('battle_wait_plan')
        if battle_wait_plan is None:
            battle_wait_plan = BattleWaitPlan()
        print(battle_wait_plan)
        # print(battle_wait_plan.sequence_function_names())
        options = runtime.pub_ctx.options
        logger.info('options: {}'.format(options))

        setup_func = getattr(self, battle_wait_plan.function_setup_name, self._bw_setup_default)
        setup_func()
        handlers = [getattr(self, func_name, None) for func_name in battle_wait_plan.sequence_function_names()]
        _hook_enabled = tuple(runtime.hook2event(h.__name__) for h in handlers if h)
        _hook_disabled = ('completion', )
        runtime.hook_enabled_update(enable=_hook_enabled, disable=_hook_disabled)
        print(f'first runtime.hook_enabled(): {runtime.hook_enabled()}')

        while True:
            self.screenshot()
            hook_enabled = runtime.hook_enabled()
            for handler in handlers:
                if runtime.hook2event(handler.__name__) not in hook_enabled:
                    continue
                result = handler()
                if handler.__name__.startswith('_bw_completion') and result == HookSignal.DONE:
                    return runtime.pub_ctx.per_battle.success == BattleResult.SUCCESS
                if result == HookSignal.CONTINUE:
                    continue



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.Component.GeneralBattle.general_battle import GeneralBattle
    c = Config('oas1')
    d = Device(c)


    class TestBattleWait(GeneralBattle, BattleWait):
        def _bw_settlement(self):
            pass

        @battle_wait_strategy( 'reserve_default', 'idle_default', failure='default')
        def battle_wait(self, *args, **kwargs):
            return self.battle_wait_with_strategy(*args, **kwargs)

    test_battle_wait = TestBattleWait(c,d)
    test_battle_wait.battle_wait(random_click_swipt_enable=1)
    with battle_wait_strategy(sequence='completion > interrupt > success > failure > idle').with_options(options={"setup": {"11": "11"}}):
        test_battle_wait.battle_wait()







