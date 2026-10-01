from __future__ import annotations

"""页面识别条件组合器。"""

from dataclasses import dataclass
from typing import Iterable, Union

from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from tasks.GameUi.common import RecognizerLike, invoke_task_callable


class Matcher:
    """页面识别条件的抽象基类。"""

    def evaluate(self, task) -> bool:
        """执行一次识别判断。

        Args:
            task: 当前运行时任务对象。

        Returns:
            识别是否成功。
        """

        raise NotImplementedError


@dataclass(frozen=True)
class AtomMatcher(Matcher):
    """最小识别单元。

    Attributes:
        target: 单个识别目标，可以是 Rule 元对象或自定义函数。
    """

    target: RecognizerLike

    def evaluate(self, task) -> bool:
        """执行单个识别目标的判断。"""

        target = self.target
        if callable(target) and not isinstance(target, (RuleImage, RuleGif, RuleOcr)):
            return bool(invoke_task_callable(target, task))
        if isinstance(target, RuleOcr):
            return bool(task.ocr_appear(target))
        if isinstance(target, (RuleImage, RuleGif)):
            return bool(task.appear(target))
        return False


@dataclass(frozen=True)
class AnyMatcher(Matcher):
    """任一子条件命中即成功。"""

    children: tuple[Matcher, ...]

    def evaluate(self, task) -> bool:
        """按“或”语义执行识别。"""

        return any(child.evaluate(task) for child in self.children)


@dataclass(frozen=True)
class AllMatcher(Matcher):
    """所有子条件都命中才成功。"""

    children: tuple[Matcher, ...]

    def evaluate(self, task) -> bool:
        """按“且”语义执行识别。"""

        return all(child.evaluate(task) for child in self.children)


@dataclass(frozen=True)
class NotMatcher(Matcher):
    """对子条件结果取反。"""

    child: Matcher

    def evaluate(self, task) -> bool:
        """执行取反识别。"""

        return not self.child.evaluate(task)


def ensure_matcher(target: Union[Matcher | RecognizerLike | Iterable[RecognizerLike] | None]) -> Matcher | None:
    """将任意识别输入规范化为 `Matcher`。

    Args:
        target: 原始识别定义，可以是 `Matcher`、Rule 元对象、可调用对象或可迭代集合。

    Returns:
        规范化后的 `Matcher`；传入 `None` 时返回 `None`。
    """

    if target is None:
        return None
    if isinstance(target, Matcher):
        return target
    if isinstance(target, (list, tuple, set)):
        return AnyMatcher(tuple(ensure_matcher(item) for item in target if item is not None))
    return AtomMatcher(target)


def any_of(*targets: RecognizerLike | Matcher) -> Matcher:
    """创建“任一命中即可”的组合识别条件。

    Args:
        *targets: 需要参与组合的识别条件。

    Returns:
        `AnyMatcher` 实例。
    """

    return AnyMatcher(tuple(ensure_matcher(target) for target in targets if target is not None))


def all_of(*targets: RecognizerLike | Matcher) -> Matcher:
    """创建“全部命中才成功”的组合识别条件。

    Args:
        *targets: 需要参与组合的识别条件。

    Returns:
        `AllMatcher` 实例。
    """

    return AllMatcher(tuple(ensure_matcher(target) for target in targets if target is not None))


def not_(target: RecognizerLike | Matcher) -> Matcher:
    """创建取反识别条件。

    Args:
        target: 需要取反的识别条件。

    Returns:
        `NotMatcher` 实例。
    """

    return NotMatcher(ensure_matcher(target))


def collect_rule_images(target: Union[Matcher | RecognizerLike | Iterable[RecognizerLike] | None]) -> tuple[RuleImage, ...]:
    """提取 matcher 树中可批量预取的 `RuleImage` 原子节点。"""

    images: list[RuleImage] = []
    seen = set()

    def visit(node):
        if node is None:
            return
        if isinstance(node, RuleImage):
            cache_key = id(node)
            if cache_key in seen:
                return
            seen.add(cache_key)
            images.append(node)
            return
        if isinstance(node, AtomMatcher):
            visit(node.target)
            return
        if isinstance(node, (AnyMatcher, AllMatcher)):
            for child in node.children:
                visit(child)
            return
        if isinstance(node, NotMatcher):
            visit(node.child)
            return
        if isinstance(node, Matcher):
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                visit(item)

    visit(target)
    return tuple(images)
