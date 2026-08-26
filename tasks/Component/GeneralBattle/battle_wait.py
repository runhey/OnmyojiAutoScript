import random
import time


from functools import wraps
from dataclasses import dataclass
from typing import TypeVar, ParamSpec

from module.logger import logger
from module.base.timer import Timer

from tasks.base_task import BaseTask


P = ParamSpec('P')
T = TypeVar('T')


@dataclass
class BattleWaitContext:
    completion = False
    success = False

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        return None

@dataclass
class BattleWaitPlan:
    """
    就是一个超级大的状态机，这里拆成了很多hook
    """
    HOOK_NAMES = ('setup', 'completion', 'interrupt', 'success', 'failure', 'reserve', 'idle')
    SEQUENCE_DEFAULT = 'completion > interrupt > success > failure > reserve > idle'
    SETUP_DEFAULT = 'default'


    def __init__(self, *arg, **kwargs):
        self.sequence = kwargs.get('sequence', BattleWaitPlan.SEQUENCE_DEFAULT)
        if not isinstance(self.sequence, str):
            raise TypeError(f'{self.sequence} is not a string')
        self.sequence: str = self.sequence.replace(' ', '').replace('\n', '').replace('\r', '').replace('setup', '')

        self.setup = kwargs.get('setup', BattleWaitPlan.SETUP_DEFAULT)
        if not isinstance(self.setup, str):
            raise TypeError(f'{self.setup} is not a string')
        for step in self.sequence.split('>'):
            if step and step not in self.HOOK_NAMES:
                continue
            value = kwargs.get(step, 'default')
            setattr(self, step, value)

    def __str__(self):
        lines = [f"{self.__class__.__name__}:", f"  sequence: {self.sequence}", "  hooks:"]
        for event_name in self.HOOK_NAMES:
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
        return f'_bw_setup_{self.setup}'

    def sequence_function_names(self) -> list[str]:
        function_names = []
        for event_name in self.sequence.split('>'):
            event_name = event_name.strip()
            if not event_name:
                continue
            if event_name not in self.HOOK_NAMES:
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

    def __call__(self, func):
        @wraps(func)
        def inner(owner, *args, **kwargs):
            # kwargs.setdefault(
            #     'battle_wait_plan',
            #     self.battle_wait_plan,
            # )
            return func(owner, battle_wait_plan=battle_wait_strategy.battle_wait_plan)

        return inner


class BattleWait(BaseTask):
    def _bw_setup_default(self, bw_ctx: BattleWaitContext):
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info('Start battle process')

    def _bw_completion_default(self, bw_ctx: BattleWaitContext):
        if bw_ctx.completion:
            logger.info('Battle done')
            return True
        return False

    def _bw_interrupt_default(self, bw_ctx: BattleWaitContext):
        pass
    def _bw_success_default(self, bw_ctx: BattleWaitContext):
        if self.appear_then_click(self.I_WIN, interval=0.8):
            return False
        appear_ghost, appear_reward, appear_gold = (
            self.appear(self.I_GREED_GHOST),
            self.appear(self.I_REWARD),
            self.appear(self.I_REWARD_GOLD)
        )
        if appear_ghost or appear_reward or appear_gold:
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
                    logger.info('Battle done')
                    bw_ctx.success = True
                    bw_ctx.completion = True
                    return True
                if timer.reached_and_reset():
                    logger.warning('battle ')
                    break
            return False
        return False

    def _bw_failure_default(self, bw_ctx: BattleWaitContext):
        if self.appear(self.I_FALSE, threshold=0.8):
            logger.warning('False battle')
            self.ui_click_until_disappear(self.I_FALSE)
            bw_ctx.completion = True
            return True
        return True
    def _bw_idle_default(self, bw_ctx: BattleWaitContext):
        pass
    def _bw_reserve_default(self, bw_ctx: BattleWaitContext):
        pass

    # idle
    # ------------------------------------------------------------------------------------------------------------------
    def _bw_idle_random_click(self, bw_ctx: BattleWaitContext):
        if 0 <= random.randint(0, 500) <= 3:  # 百分之4的概率
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

    # ------------------------------------------------------------------------------------------------------------------
    def battle_wait_v3(self, *args, **kwargs) -> bool:
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
                if handler.__name__ == '_bw_completion_default' and result:
                    return True



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.Component.GeneralBattle.general_battle import GeneralBattle
    c = Config('oas1')
    d = Device(c)


    class TestBattleWait(GeneralBattle, BattleWait):
        def _bw_settlement(self):
            pass

        @battle_wait_strategy(idle='default', failure='default', sequence='idle > reserve> yyy > failure > completion')
        def battle_wait(self, *args, **kwargs):
            return self.battle_wait_v3(*args, **kwargs)

    test_battle_wait = TestBattleWait(c,d)
    test_battle_wait.battle_wait(random_click_swipt_enable=1)
    with battle_wait_strategy(sequence='idle > failure'):
        test_battle_wait.battle_wait()













