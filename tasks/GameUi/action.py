from __future__ import annotations

"""页面动作与 hook 动作的组合器。"""

from dataclasses import dataclass

from tasks.GameUi.common import ActionLike, RecognizerLike
from tasks.GameUi.matcher import Matcher, ensure_matcher


@dataclass(frozen=True)
class ActionSequence:
    """顺序执行的一组动作。

    Attributes:
        actions: 按顺序执行的动作集合。
        success_index: 使用哪个动作的执行结果作为整个序列的成功判定。
    """

    actions: tuple[ActionLike, ...]
    success_index: int = 0


@dataclass(frozen=True)
class ConditionalAction:
    """带前置条件的动作包装器。

    Attributes:
        condition: 需要先命中的识别条件。
        action: 条件满足后执行的动作。
    """

    condition: Matcher
    action: ActionLike


def sequence(*actions: ActionLike, success_index: int = 0) -> ActionSequence:
    """创建一个顺序动作序列。

    Args:
        *actions: 需要顺序执行的动作。
        success_index: 作为整体成功判定的动作索引。

    Returns:
        `ActionSequence` 实例。
    """

    return ActionSequence(tuple(actions), success_index=success_index)


def conditional_action(condition: RecognizerLike | Matcher, action: ActionLike) -> ConditionalAction:
    """创建带条件的动作。

    Args:
        condition: 前置识别条件。
        action: 条件满足后执行的动作。

    Returns:
        `ConditionalAction` 实例。

    Raises:
        ValueError: 当条件为空时抛出。
    """

    matcher = ensure_matcher(condition)
    if matcher is None:
        raise ValueError("conditional_action requires a valid condition")
    return ConditionalAction(matcher, action)
