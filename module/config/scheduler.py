# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import datetime
import operator

from cached_property import cached_property

from module.base.filter import Filter

from module.config.config_manual import ConfigManual
from module.logger import logger

from tasks.Script.config_optimization import ScheduleRule


class TaskScheduler:
    filter = Filter(regex=r"(.*)", attr=["command"])
    filter.load(ConfigManual.SCHEDULER_PRIORITY)

    @staticmethod
    def schedule(rule: ScheduleRule, pending: list["Function"]) -> list["Function"]:
        """
        执行 任务的调度
        :param rule:
        :param pending:
        :return:
        """
        if rule != ScheduleRule.FILTER and rule != ScheduleRule.FIFO and rule != ScheduleRule.PRIORITY:
            logger.error(f"Invalid rule: {rule}")
            return pending
        if isinstance(pending, list) is False:
            logger.error(f"Invalid pending: {pending}")
            return pending

        # 第一种
        if rule == ScheduleRule.FILTER:
            pending_task = TaskScheduler.filter.apply(pending)
            return pending_task

        # 第二种
        if rule == ScheduleRule.FIFO:
            pending_task = TaskScheduler.fifo(pending)
            return pending_task

        # 第三种
        if rule == ScheduleRule.PRIORITY:
            pending_task = TaskScheduler.priority(pending)
            return pending_task

    @staticmethod
    def fifo(pending: list["Function"]) -> list["Function"]:
        """
        先来后到，（按照任务的先后顺序进行调度）
        :param pending:
        :return:
        """
        tasks_pending = sorted(pending, key=operator.attrgetter("next_run"))
        for task in tasks_pending:
            # 永远保证 Restart 任务在第一个
            if task.command == 'Restart':
                tasks_pending.remove(task)
                tasks_pending.insert(0, task)
                break
        return tasks_pending

    @staticmethod
    def priority(pending: list["Function"]) -> list["Function"]:
        """
        基于优先级，同一个优先级的任务按照先来后到的顺序进行调度，优先级高的任务先调度
        :param pending:
        :return:
        """
        # 1. 按照优先级进行分组
        sorted(pending, key=operator.attrgetter("priority"))
        groups = {}
        for task in pending:
            if groups.get(task.priority) is None:
                groups[task.priority] = []
            groups[task.priority].append(task)
        # 2. 对每一组进行先来后到的排序
        for priority, tasks in groups.items():
            groups[priority] = TaskScheduler.fifo(tasks)

        # 3.按照顺序合并所有的任务
        tasks_pending = []
        for priority in sorted(groups.keys()):
            tasks_pending.extend(groups[priority])

        return tasks_pending


# 测试代码
if __name__ == '__main__':
    pass

