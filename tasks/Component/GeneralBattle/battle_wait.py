import random
import time


from functools import wraps
from dataclasses import dataclass
from typing import TypeVar, ParamSpec, Callable
from enum import Enum, auto

from module.logger import logger
from module.base.timer import Timer

from tasks.base_task import BaseTask


P = ParamSpec('P')
T = TypeVar('T')


class HookSignal(Enum):
    CONTINUE = auto()  # 无事发生
    BUSY = auto()  # 处理了，继续
    DONE = auto()  # 流程结束

@dataclass
class BattleWaitContext:
    completion = False
    success = False

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        return None

class BattleWaitPlan:
    """
    就是一个超级大的状态机，这里拆成了很多hook
    """
    HOOKS_DEFAULT = ('setup', 'completion', 'interrupt', 'success', 'failure', 'idle')
    SEQUENCE_DEFAULT = 'completion > interrupt > success > failure >'

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
    使用with 上下文临时修改  battle_wait_plan
    首次装饰 func 初始化 battle_wait_plan
    """
    battle_wait_plan: BattleWaitPlan = None


    def __init__(self, *arg, **kwargs):
        self._temp_battle_wait_plan = None
        if battle_wait_strategy.battle_wait_plan is None:
            # 首次装饰 func 初始化 battle_wait_plan
            battle_wait_strategy.battle_wait_plan = BattleWaitPlan(*arg, **kwargs)  # pylint: disable=unused-argument
        elif self._temp_battle_wait_plan is None:
            # 使用 with 上下文临时修改 battle_wait_plan
            self._temp_battle_wait_plan = BattleWaitPlan(*arg, **kwargs)

    def __enter__(self):
        self._previous_plan = battle_wait_strategy.battle_wait_plan

        if self._temp_battle_wait_plan is not None:
            battle_wait_strategy.battle_wait_plan = self._temp_battle_wait_plan
        return self

    def __exit__(self, *exc):
        battle_wait_strategy.battle_wait_plan = self._previous_plan
        return False

    def __str__(self):
        temp_plan = getattr(self, '_temp_battle_wait_plan', None)
        default_plan = getattr(self, 'battle_wait_plan', None)

        if temp_plan is not None:
            plan = temp_plan
            scope = 'temporary'
        else:
            plan = default_plan
            scope = 'decorator'

        if plan is None:
            return f'{type(self).__name__}(plan=None)'

        return (
            f'{type(self).__name__}('
            f'scope={scope}, '
            f'plan=\n{plan}'
            f')'
        )
    def __repr__(self):
        return self.__str__()


    def _recreate_cm(self):
        return self

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
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
                battle_wait_strategy.battle_wait_plan =\
                    battle_wait_strategy.battle_wait_plan.override(*override_args)
            # -----------------------------------------------------------------------
            # kwargs.setdefault(
            #     'battle_wait_plan',
            #     self.battle_wait_plan,
            # )
            return func(owner, battle_wait_plan=battle_wait_strategy.battle_wait_plan)

        return inner


class BattleWait(BaseTask):
    # build in
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_setup_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info('Start battle process')
        return HookSignal.DONE

    def _bw_completion_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        if bw_ctx.completion:
            logger.info('Battle done')
            return HookSignal.DONE
        return HookSignal.CONTINUE

    def _bw_interrupt_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        return HookSignal.CONTINUE

    def _bw_success_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        if self.appear_then_click(self.I_WIN, interval=0.8):
            return HookSignal.CONTINUE
        appear_ghost, appear_reward, appear_gold = (
            self.appear(self.I_GREED_GHOST),
            self.appear(self.I_REWARD),
            self.appear(self.I_REWARD_GOLD)
        )
        if not any([appear_ghost, appear_reward, appear_gold]):
            return HookSignal.CONTINUE
        logger.info('Win battle')
        timer = Timer(20).start()
        while 1:
            self.screenshot()

            _appear_ghost, _appear_reward, _appear_gold = (
                self.appear(self.I_GREED_GHOST, threshold=0.6),
                self.appear(self.I_REWARD),
                self.appear(self.I_REWARD_GOLD)
            )
            # logger.info(f'_appear_ghost: {_appear_ghost} _appear_reward: {_appear_reward} _appear_gold: {_appear_gold}')
            if any([_appear_ghost, _appear_reward, _appear_gold]):
                action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                self.click(action_click, interval=1.5)
            else:
                logger.info('Get all reward')
                bw_ctx.success = True
                bw_ctx.completion = True
                return HookSignal.CONTINUE
            if timer.reached_and_reset():
                logger.warning('battle ')
                break
        return HookSignal.CONTINUE


    def _bw_failure_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        if self.appear(self.I_FALSE, threshold=0.8):
            logger.warning('False battle')
            self.ui_click_until_disappear(self.I_FALSE)
            bw_ctx.completion = True
            return True
        return True

    def _bw_idle_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        return HookSignal.CONTINUE

    def _bw_reserve_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        return HookSignal.CONTINUE

    def _bw_randomclick_default(self, bw_ctx: BattleWaitContext) -> HookSignal:
        if 0 <= random.randint(0, 500) <= 20:  # 百分之4的概率
            rand_type = random.randint(0, 2)
            match rand_type:
                case 0:
                    self.click(self.C_RANDOM_CLICK, interval=20)
                case 1:
                    self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
                case 2:
                    self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
            # 重新设置为长战斗
            # self.device.stuck_record_add('BATTLE_STATUS_S')
        else:
            time.sleep(0.4)  # 这样的好像不对
        return HookSignal.CONTINUE

    # custom
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_success_soul(self, bw_ctx: BattleWaitContext) -> HookSignal:
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
                action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                self.click(action_click, interval=1.5)
            else:
                logger.info('Get all reward')
                bw_ctx.success = True
                bw_ctx.completion = True
                return HookSignal.CONTINUE
            if timer.reached_and_reset():
                logger.warning('battle ')
                break
        return HookSignal.CONTINUE


    # def _bw_idle_random_click(self, bw_ctx: BattleWaitContext):
    #     if 0 <= random.randint(0, 500) <= 3:  # 百分之4的概率
    #         rand_type = random.randint(0, 2)
    #         match rand_type:
    #             case 0:
    #                 self.click(self.C_RANDOM_CLICK, interval=20)
    #             case 1:
    #                 self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
    #             case 2:
    #                 self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
    #         # 重新设置为长战斗
    #         # self.device.stuck_record_add('BATTLE_STATUS_S')
    #     else:
    #         time.sleep(0.4)  # 这样的好像不对
    #
    # def _bw_random_click(self, bw_ctx: BattleWaitContext):
    #     if 0 <= random.randint(0, 500) <= 3:  # 百分之4的概率
    #         rand_type = random.randint(0, 2)
    #         match rand_type:
    #             case 0:
    #                 self.click(self.C_RANDOM_CLICK, interval=20)
    #             case 1:
    #                 self.swipe(self.S_BATTLE_RANDOM_LEFT, interval=20)
    #             case 2:
    #                 self.swipe(self.S_BATTLE_RANDOM_RIGHT, interval=20)
    #         # 重新设置为长战斗
    #         # self.device.stuck_record_add('BATTLE_STATUS_S')
    #     else:
    #         time.sleep(0.4)  # 这样的好像不对

    # ------------------------------------------------------------------------------------------------------------------
    def battle_wait_with_strategy(self, *args, **kwargs) -> bool:
        """
        三种自定义配置方法：
        1. 使用装饰器battle_wait_strategy
            @battle_wait_strategy( 'reserve_default', 'idle_default', failure='default')
            def battle_wait(self, *args, **kwargs):
                return self.battle_wait_with_strategy(*args, **kwargs)
        2. 使用 with 上下文 （！在1基础上）
            with battle_wait_strategy('reserve_default'):
                test_battle_wait.battle_wait()
        3. 调用时动态传参 （！在2基础上）
            obj.battle_wait(random_click_swipt_enable=1)  # 详细参数看 battle_wait_strategy.__call__()

        理解 event + strategy 概念： 把战斗过程抽象为一系列触发事件以及对应的实现函数，也称hook。
        默认定义的 hook 有 BattleWaitPlan.HOOKS_DEFAULT = ('setup', 'completion', 'interrupt', 'success', 'failure', 'idle')
        这些 hook 跑在一个 while 里面，默认的调用顺序 BattleWaitPlan.SEQUENCE_DEFAULT = 'completion > interrupt > success > failure > idle'
        setup 没有跑在 while里面 而是在 while之前

        event + strategy 拼成了一个hook, 一个 event 在一次战斗过程中只能挂载一个 strategy】
        自定义hook就是字符串拼起来：  battle_wait_strategy的入参可以有 ‘event_strategy’ 或者 'event=strategy'
        可以添加任意 event 以及其对应的 strategy。比如 ‘yyy_default’ 'abcd_edf'
        但是必须要实现对应的hook 上面的比如 _bw_yyy_default() 以及 _bw_abcd_edf()

        hook 可以自定义顺序，比如 battle_wait_strategy(sequence='completion > interrupt > success > failure > idle')
        如果指定sequence， 新增的event会按照传参时候从左到右排序，左边高优先级，新增的会插入到 failure 和 idle 之间
        """
        battle_wait_plan = kwargs.get('battle_wait_plan')
        if battle_wait_plan is None:
            battle_wait_plan = BattleWaitPlan()
        # print(battle_wait_plan)
        # print(battle_wait_plan.sequence_function_names())

        bw_ctx = BattleWaitContext()
        setup_func = getattr(self, battle_wait_plan.function_setup_name, self._bw_setup_default)
        setup_func(bw_ctx)
        handlers = [getattr(self, func_name, None) for func_name in battle_wait_plan.sequence_function_names()]

        while True:
            self.screenshot()
            for handler in handlers:
                result = handler(bw_ctx)
                if handler.__name__.startswith('_bw_completion') and result == HookSignal.DONE:
                    return True

            # bw_ctx.completion = True



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
    with battle_wait_strategy(sequence='completion > interrupt > success > failure > idle'):
        test_battle_wait.battle_wait()













