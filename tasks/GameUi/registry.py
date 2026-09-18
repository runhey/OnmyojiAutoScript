from __future__ import annotations

"""页面注册表。"""

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tasks.GameUi.page_definition import Page


class PageRegistry:
    """进程级静态页面注册表。

    该注册表只保存页面定义，不保存任务运行时状态。
    """

    # 所有静态页面定义，key 为页面唯一标识。
    _pages: dict[str, "Page"] = {}
    # 已加载过的页面模块，避免重复导入。
    _loaded_modules: set[str] = set()
    # 是否完成一次全量页面扫描。
    _page_modules_loaded = False

    @classmethod
    def register(cls, page: "Page") -> "Page":
        """注册一个静态页面定义。

        Args:
            page: 待注册的页面定义。

        Returns:
            原始页面对象，便于链式使用。
        """

        cls._pages[page.key] = page
        return page

    @classmethod
    def get(cls, key: str) -> "Page | None":
        """按页面 key 获取页面定义。

        Args:
            key: 页面唯一标识。

        Returns:
            页面定义；不存在时返回 `None`。
        """

        return cls._pages.get(key)

    @classmethod
    def all(cls, categories: set[str] = None) -> list["Page"]:
        """获取所有或指定分类的页面定义。

        Args:
            categories: 允许返回的页面分类集合；为空时返回全部页面。

        Returns:
            页面定义列表。
        """

        pages = list(cls._pages.values())
        if not categories:
            return pages
        return [page for page in pages if page.category in categories]

    @classmethod
    def load_all_pages(cls) -> None:
        """扫描并导入 `tasks/*/page.py`

        该方法只会执行一次，用于构建静态页面注册表。
        """

        if cls._page_modules_loaded:
            return
        base_dir = Path(__file__).resolve().parent.parent
        for task_dir in base_dir.iterdir():
            if not task_dir.is_dir():
                continue
            for module_name in ("page"):
                module_file = task_dir / f"{module_name}.py"
                if not module_file.exists():
                    continue
                import_name = f"tasks.{task_dir.name}.{module_name}"
                if import_name in cls._loaded_modules:
                    continue
                importlib.import_module(import_name)
                cls._loaded_modules.add(import_name)
        cls._page_modules_loaded = True
