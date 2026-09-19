from __future__ import annotations

"""页面导航的任务级运行时 session。"""

from dataclasses import dataclass, field

from tasks.GameUi.page_definition import Page, Transition
from tasks.GameUi.registry import PageRegistry


@dataclass
class NavigatorSession:
    """当前任务的导航运行时上下文。

    Attributes:
        task_category: 当前任务所属分类。
        current_page: 最近一次稳定识别到的当前页面。
        edge_penalties: 边失败惩罚值，key 为边 key。
        local_unknown_closers: 当前任务追加的未知页关闭动作。
        pages: 当前任务 session 中可见的页面快照。
        unknown_close_history: 未知页关闭尝试历史，用于超时诊断。
        last_enter_success_page_key: 上一次触发进入成功 hook 的页面 key。
    """

    task_category: str
    current_page: Page | None = None
    edge_penalties: dict[str, float] = field(default_factory=dict)
    local_unknown_closers: list = field(default_factory=list)
    pages: dict[str, Page] = field(default_factory=dict)
    unknown_close_history: list[str] = field(default_factory=list)
    last_enter_success_page_key: str | None = None

    def bootstrap(self, pages: list[Page]) -> None:
        """使用静态页面定义初始化当前 session。

        Args:
            pages: 全量静态页面定义列表。
        """

        self.pages = self._snapshot_pages(pages)

    def _snapshot_pages(self, source_pages: list[Page]) -> dict[str, Page]:
        """将静态页面定义复制为 session 页面快照。

        Args:
            source_pages: 静态页面定义列表。

        Returns:
            以页面 key 为索引的页面副本字典。
        """

        cloned_pages = {page.key: page.clone() for page in source_pages}
        for page in source_pages:
            cloned_page = cloned_pages[page.key]
            for transition in page.transitions:
                destination = cloned_pages.get(transition.destination.key)
                if destination is None:
                    continue
                cloned_page.connect(
                    destination,
                    transition.action,
                    cost=transition.cost,
                    key=transition.key,
                    on_enter_success=transition.on_enter_success,
                    on_enter_failure=transition.on_enter_failure,
                    on_leave_success=transition.on_leave_success,
                    on_leave_failure=transition.on_leave_failure,
                )
        return cloned_pages

    def all_pages(self, categories: set[str] = None) -> list[Page]:
        """读取当前 session 中允许访问的页面列表。

        Args:
            categories: 允许返回的页面分类集合；为空时返回全部 session 页面。

        Returns:
            页面列表。
        """

        pages = list(self.pages.values())
        if not categories:
            return pages
        return [page for page in pages if page.category in categories]

    def add_page(self, page: Page) -> Page:
        """向当前 session 追加一个动态页面。

        Args:
            page: 页面定义对象。

        Returns:
            session 内可用的页面副本。
        """

        current = self.pages.get(page.key)
        if current is not None:
            return current

        cloned_page = page.clone()
        self.pages[cloned_page.key] = cloned_page
        for transition in page.transitions:
            destination = self.resolve_page(transition.destination)
            if destination is None:
                destination = self.add_page(transition.destination)
            cloned_page.connect(
                destination,
                transition.action,
                cost=transition.cost,
                key=transition.key,
                on_enter_success=transition.on_enter_success,
                on_enter_failure=transition.on_enter_failure,
                on_leave_success=transition.on_leave_success,
                on_leave_failure=transition.on_leave_failure,
            )
        return cloned_page

    def resolve_page(self, page: Page | None) -> Page | None:
        """将静态页面定义解析为当前 session 页面副本。

        Args:
            page: 待解析的页面定义。

        Returns:
            session 页面对象；无法解析时返回 `None`。
        """

        if page is None:
            return None

        current = self.pages.get(page.key)
        if current is not None:
            return current

        registry_page = PageRegistry.get(page.key)
        if registry_page is not None:
            return self.add_page(registry_page)
        return None

    def add_unknown_closer(self, *actions) -> None:
        """为当前任务追加未知页关闭动作。

        Args:
            *actions: 额外的关闭动作。
        """

        self.local_unknown_closers.extend(action for action in actions if action is not None)

    def add_penalty(self, transition: Transition, value: float = 1.0) -> float:
        """增加一条边的失败惩罚。

        Args:
            transition: 失败的边。
            value: 本次增加的惩罚值。

        Returns:
            增加后的总惩罚值。
        """

        self.edge_penalties[transition.key] = self.edge_penalties.get(transition.key, 0.0) + value
        return self.edge_penalties[transition.key]

    def penalty_of(self, transition: Transition) -> float:
        """读取某条边的当前惩罚值。

        Args:
            transition: 目标边。

        Returns:
            当前惩罚值。
        """

        return self.edge_penalties.get(transition.key, 0.0)
