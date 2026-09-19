from __future__ import annotations

"""GameUi 运行时的共享类型与工具函数。"""

import inspect
import re
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr

if TYPE_CHECKING:
    from tasks.GameUi.action import ConditionalAction, ActionSequence
else:
    ConditionalAction = Any
    ActionSequence = tuple[Any]

# 页面识别条件允许直接使用现有 Rule 元对象或自定义函数。
RecognizerLike = RuleImage | RuleGif | RuleOcr | Callable
# 页面跳转动作和 hook 动作允许使用点击类元对象、自定义函数或组合动作。
ActionLike = RuleImage | RuleGif | RuleOcr | RuleList | RuleClick | ActionSequence | ConditionalAction | Callable


def camel_to_snake(value: str) -> str:
    """将驼峰或混合命名转换为下划线命名。

    Args:
        value: 待转换的字符串。

    Returns:
        转换后的下划线命名字符串。
    """

    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.replace("-", "_").lower()


def infer_stack_symbol(stack_depth: int = 3) -> str:
    """根据调用栈推断页面变量名。

    Args:
        stack_depth: 需要读取的调用栈深度，默认与页面定义调用层一致。

    Returns:
        推断出的变量名；若无法解析则返回基于行号的兜底名称。
    """

    filename, line_number, function_name, text = traceback.extract_stack()[-stack_depth]
    del filename, function_name
    if text and "=" in text:
        return text[: text.find("=")].strip()
    return f"page_{line_number}"


def infer_page_key_and_name(stack_depth: int = 4) -> tuple[str, str]:
    """从调用栈中推断页面的 `key` 与 `name`。

    Args:
        stack_depth: 需要向上回溯的调用栈深度。`Page.__init__ -> infer_page_key_and_name
            -> infer_stack_symbol` 这一层级下，默认值 4 才能落到真正的页面定义语句。

    Returns:
        一个 `(page_key, page_name)` 元组。
    """

    symbol = infer_stack_symbol(stack_depth=stack_depth)
    name = symbol.split(".")[-1]
    return symbol, name


def infer_tasks_category_from_parts(parts: list[str], task_index: int, *, component_use_child: bool = False) -> str:
    """根据包含 `tasks` 的路径片段推断分类。

    Args:
        parts: 已拆分的路径或模块名片段。
        task_index: 片段列表中 `tasks` 所在的索引。
        component_use_child: 当目标目录为 `Component` 时，是否继续使用下一层目录名作为分类。

    Returns:
        推断出的分类名。
    """

    if task_index + 1 >= len(parts):
        return "global"

    folder = parts[task_index + 1]
    if folder == "GameUi":
        return "global"
    if component_use_child and folder == "Component" and task_index + 2 < len(parts):
        return camel_to_snake(parts[task_index + 2])
    return camel_to_snake(folder)


def infer_tasks_category_from_path(path: str | Path, *, component_use_child: bool = False) -> str:
    """根据绝对或相对路径推断任务分类。

    Args:
        path: 目标文件路径。
        component_use_child: 当路径位于 `tasks/Component/*` 下时，是否继续使用下一层目录名作为分类。

    Returns:
        推断出的分类名；路径不在 `tasks` 目录下时返回 `global`。
    """

    parts = list(Path(path).resolve().parts)
    if "tasks" not in parts:
        return "global"
    return infer_tasks_category_from_parts(parts, parts.index("tasks"), component_use_child=component_use_child)


def infer_category(filename: str | None = None, stack_depth: int = 3) -> str:
    """根据文件路径推断页面分类。

    Args:
        filename: 显式传入的文件路径；为空时从调用栈推断。
        stack_depth: 当 `filename` 为空时，读取调用栈的深度。

    Returns:
        页面所属分类；`tasks/GameUi` 内的页面固定归为 `global`。
    """

    return infer_tasks_category_from_path(filename or traceback.extract_stack()[-stack_depth].filename)


def invoke_task_callable(target: Callable, task):
    """调用用户自定义识别函数或 hook 函数。

    Args:
        target: 用户传入的可调用对象。
        task: 当前运行时任务对象。

    Returns:
        目标函数的返回值。
    """

    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return target(task)
    if len(signature.parameters) <= 0:
        return target()
    return target(task)
