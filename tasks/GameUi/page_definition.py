from __future__ import annotations

"""页面与边定义模型。"""

from dataclasses import dataclass, field
from typing import Iterable, Union

from tasks.GameUi.common import ActionLike, RecognizerLike, infer_category, infer_page_key_and_name
from tasks.GameUi.matcher import Matcher, ensure_matcher
from tasks.GameUi.registry import PageRegistry
from module.logger import logger


def _clamp_priority(value: int, page_key: str) -> int:
    """将页面优先级约束到合法范围。"""

    priority = max(1, min(100, value))
    if priority != value:
        logger.warning(f"Page priority out of range: key={page_key}, value={value}, clamped={priority}")
    return priority


def sort_pages_by_priority(indexed_pages: Iterable[tuple[int, "Page"]]) -> list["Page"]:
    """按优先级降序、注册顺序升序稳定排序页面候选。"""

    ordered_pages = sorted(indexed_pages, key=lambda item: (-item[1].priority, item[0]))
    return [page for _, page in ordered_pages]


@dataclass
class Transition:
    """页面间的一条有向边。

    Attributes:
        source: 起点页面。
        destination: 终点页面。
        action: 从起点前往终点时执行的动作。
        cost: 边的额外代价。
        key: 边的唯一标识；为空时自动生成。
        on_enter_success: 到达终点成功后的边级 hook。
        on_enter_failure: 到达终点失败后的边级 hook。
        on_leave_success: 成功离开起点后的边级 hook。
        on_leave_failure: 离开起点失败后的边级 hook。
    """

    source: "Page"
    destination: "Page"
    action: ActionLike
    cost: float = 0.0
    key: str | None = None
    on_enter_success: list[ActionLike] = field(default_factory=list)
    on_enter_failure: list[ActionLike] = field(default_factory=list)
    on_leave_success: list[ActionLike] = field(default_factory=list)
    on_leave_failure: list[ActionLike] = field(default_factory=list)

    def __post_init__(self):
        """补齐未显式提供的边 key。"""

        if self.key is None:
            self.key = f"{self.source.key}->{self.destination.key}#{len(self.source.transitions)}"

    def hooks(self, stage: str) -> list[ActionLike]:
        """按阶段读取边级 hook 列表。

        Args:
            stage: hook 阶段名。

        Returns:
            对应阶段的 hook 列表。
        """

        return getattr(self, stage)


class Page:
    """页面定义对象。

    页面定义只描述静态信息：识别条件、页面分类、进入/离开 hook 与可达边。
    运行时状态会在 `NavigatorSession` 中保存。
    """

    def __init__(
        self,
        recognizer: Union[Matcher, RecognizerLike, Iterable[RecognizerLike]],
        *,
        key: str | None = None,
        name: str | None = None,
        category: str | None = None,
        priority: int = 50,
        cost: float = 1.0,
        register: bool = True,
    ):
        """初始化页面定义。

        Args:
            recognizer: 页面识别条件，可以是 `Matcher`、Rule 元对象、自定义函数或可迭代集合。
            key: 页面唯一标识；为空时根据页面变量名自动推断。
            name: 页面展示名称；为空时根据页面变量名自动推断。
            category: 页面分类；为空时根据文件路径自动推断。
            priority: 页面识别优先级，范围 1-100。
            cost: 页面代价，供 Dijkstra 路径规划使用。
            register: 是否注册到全局 `PageRegistry`。动态页面应传入 `False`。
        """

        inferred_key, inferred_name = infer_page_key_and_name()
        # 页面唯一标识，用于 session 拷贝、路由和日志。
        self.key = key or inferred_key
        # 页面展示名称，用于日志输出。
        self.name = name or inferred_name
        # 页面所属分类，`tasks/GameUi` 内默认归类为 global。
        self.category = category or infer_category()
        # 页面识别优先级，越大越先参与复验。
        self.priority = _clamp_priority(priority, self.key)
        # 页面进入该节点的基础代价。
        self.cost = cost
        # 规范化后的页面识别条件。
        self.recognizer = ensure_matcher(recognizer)
        # 从当前页面出发的所有有向边。
        self.transitions: list[Transition] = []
        # 识别到当前页面并稳定进入后的页面级 hook。
        self.on_enter_success: list[ActionLike] = []
        # 目标页面进入失败后的页面级 hook。
        self.on_enter_failure: list[ActionLike] = []
        # 成功离开当前页面后的页面级 hook。
        self.on_leave_success: list[ActionLike] = []
        # 离开当前页面失败后的页面级 hook。
        self.on_leave_failure: list[ActionLike] = []
        if register:
            PageRegistry.register(self)

    def __eq__(self, other):
        """按页面 key 判断相等性。"""

        return isinstance(other, Page) and self.key == other.key

    def __hash__(self):
        """使页面对象可作为字典 key 或集合元素。"""

        return hash(self.key)

    def __str__(self):
        """返回页面展示名称。"""

        return self.name

    def connect(
        self,
        destination: "Page",
        action: ActionLike,
        *,
        cost: float = 0.0,
        key: str | None = None,
        on_enter_success: Iterable[ActionLike] = None,
        on_enter_failure: Iterable[ActionLike] = None,
        on_leave_success: Iterable[ActionLike] = None,
        on_leave_failure: Iterable[ActionLike] = None,
    ) -> Transition:
        """声明从当前页面到目标页面的一条边。

        Args:
            destination: 边的终点页面。
            action: 尝试跳转时执行的动作。
            cost: 边的额外代价。
            key: 边的唯一标识；为空时自动生成。
            on_enter_success: 边级进入成功 hook。
            on_enter_failure: 边级进入失败 hook。
            on_leave_success: 边级离开成功 hook。
            on_leave_failure: 边级离开失败 hook。

        Returns:
            新建或替换后的 `Transition` 对象。
        """

        transition = Transition(
            source=self,
            destination=destination,
            action=action,
            cost=cost,
            key=key,
            on_enter_success=list(on_enter_success or []),
            on_enter_failure=list(on_enter_failure or []),
            on_leave_success=list(on_leave_success or []),
            on_leave_failure=list(on_leave_failure or []),
        )
        if transition.key is not None:
            self.transitions = [item for item in self.transitions if item.key != transition.key]
        self.transitions.append(transition)
        return transition

    def remove_transition(self, *, destination: "Page | None" = None, key: str | None = None) -> None:
        """删除页面边。

        Args:
            destination: 按目标页面删除边。
            key: 按边 key 删除边。
        """

        remained = []
        for transition in self.transitions:
            if key is not None and transition.key == key:
                continue
            if destination is not None and transition.destination == destination:
                continue
            remained.append(transition)
        self.transitions = remained

    def clear_transitions(self) -> None:
        """清空当前页面的所有出边。"""

        self.transitions = []

    def hooks(self, stage: str) -> list[ActionLike]:
        """按阶段读取页面级 hook 列表。

        Args:
            stage: hook 阶段名。

        Returns:
            对应阶段的 hook 列表。
        """

        return getattr(self, stage)

    def add_hooks(self, stage: str, *actions: ActionLike):
        """为指定阶段追加 hook。

        Args:
            stage: hook 阶段名。
            *actions: 需要追加的动作。

        Returns:
            当前页面对象，便于链式调用。
        """

        hooks = self.hooks(stage)
        hooks.extend(action for action in actions if action is not None)
        return self

    def add_enter_success_hooks(self, *actions: ActionLike):
        """追加进入成功 hook。"""

        return self.add_hooks("on_enter_success", *actions)

    def add_enter_failure_hooks(self, *actions: ActionLike):
        """追加进入失败 hook。"""

        return self.add_hooks("on_enter_failure", *actions)

    def add_leave_success_hooks(self, *actions: ActionLike):
        """追加离开成功 hook。"""

        return self.add_hooks("on_leave_success", *actions)

    def add_leave_failure_hooks(self, *actions: ActionLike):
        """追加离开失败 hook。"""

        return self.add_hooks("on_leave_failure", *actions)

    def clone(self) -> "Page":
        """拷贝一个不注册到全局表的页面副本。

        Returns:
            仅复制静态定义和页面级 hook 的页面副本。
        """

        page = Page(
            self.recognizer,
            key=self.key,
            name=self.name,
            category=self.category,
            priority=self.priority,
            cost=self.cost,
            register=False,
        )
        page.on_enter_success = list(self.on_enter_success)
        page.on_enter_failure = list(self.on_enter_failure)
        page.on_leave_success = list(self.on_leave_success)
        page.on_leave_failure = list(self.on_leave_failure)
        return page
