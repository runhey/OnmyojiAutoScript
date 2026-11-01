"""Configuration API declarations and the stateful worker runtime.

The operation methods live in ``ConfigModMixin`` so the GUI facade can reuse
the same decorated API without inheriting worker cache or lock state.
``ConfigMod`` combines that API with ``ConfigAccessState`` for Worker usage.
"""

from __future__ import annotations

from typing import Any

from oas.config.entry.mod_config import modconfig
from oas.config.entry.model import ConfigSetEvent, ModelConfigRef
from oas.config.runtime.config_state import ConfigAccessState
from oas.mod.info import ModEntryInfo


class ConfigModMixin:
    """Stateless declarations of the configuration operation API.

    Methods receive ``config_name`` explicitly and return the value computed
    by ``modconfig``.  This class deliberately owns no configuration cache,
    database handle, lock, or pending-change state.
    """

    # ------------------------------------------------------------------
    # Runtime storage access
    # ------------------------------------------------------------------

    @modconfig.config_snapshot()
    def _config_snapshot(
        self,
        result: tuple[list[Any], tuple[int, int]],
        config_name: str,
    ) -> tuple[list[Any], tuple[int, int]]:
        """Read configuration rows and their SQLite data version."""
        return result

    @modconfig.config_data_version()
    def _config_data_version(
        self,
        result: tuple[int, int],
        config_name: str,
    ) -> tuple[int, int]:
        """Read the SQLite data version for a configuration database."""
        return result

    # ------------------------------------------------------------------
    # config_*：Alasio 兼容接口
    # ------------------------------------------------------------------

    @modconfig.config_read()
    def config_read(
        self,
        result: dict[str, dict[str, dict[str, Any]]],
        config_name: str,
        ref: ModelConfigRef,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """读取 ref 选中的 Task/Group，缺失的 Group 用模型默认值补齐。"""
        return result

    @modconfig.config_batch_set()
    def config_batch_set(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        events: list[ConfigSetEvent],
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """批量设置参数；任一参数校验失败则整批不写入。"""
        return result

    @modconfig.config_set()
    def config_set(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        event: ConfigSetEvent,
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """设置单个参数，语义与 ``config_batch_set`` 相同。"""
        return result

    @modconfig.config_batch_reset()
    def config_batch_reset(
        self,
        result: list[ConfigSetEvent],
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> list[ConfigSetEvent]:
        """批量把参数恢复为模型默认值。"""
        return result

    @modconfig.config_reset()
    def config_reset(
        self,
        result: ConfigSetEvent | None,
        config_name: str,
        event: ConfigSetEvent,
    ) -> ConfigSetEvent | None:
        """把单个参数恢复为模型默认值。"""
        return result

    @modconfig.config_group_batch_reset()
    def config_group_batch_reset(
        self,
        result: list[ConfigSetEvent],
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> list[ConfigSetEvent]:
        """批量重置整个 Group；``event.arg`` 不参与。"""
        return result

    @modconfig.config_group_reset()
    def config_group_reset(
        self,
        result: list[ConfigSetEvent],
        config_name: str,
        event: ConfigSetEvent,
    ) -> list[ConfigSetEvent]:
        """重置单个 Group。"""
        return result

    # ------------------------------------------------------------------
    # cfg_*：OAS 原生生命周期接口
    # ------------------------------------------------------------------

    @modconfig.cfg_task_add()
    def cfg_task_add(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        taskclass: str,
        name: str = 'default',
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """新增 Task 实例，数据库中的名字为 ``taskclass@name``。"""
        return result

    @modconfig.cfg_task_del()
    def cfg_task_del(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """删除一个 Task 实例及它的全部 Group 行。"""
        return result

    @modconfig.cfg_task_copy()
    def cfg_task_copy(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        new_name: str = 'default',
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """复制 Task 实例，保留当前值，目标名为 ``TaskClass@new_name``。"""
        return result

    @modconfig.cfg_task_reset()
    def cfg_task_reset(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """把一个 Task 实例的全部 Group 恢复为模型默认值。"""
        return result

    @modconfig.cfg_group_add()
    def cfg_group_add(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
        groupclass: str,
        index: int | None = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """新增一个 Group；动态 Group 用 ``index`` 指定插入位置，缺省追加。"""
        return result

    @modconfig.cfg_group_del()
    def cfg_group_del(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """删除一个 Group 的配置行；动态实例用 ``字段@序号`` 定位。"""
        return result

    @modconfig.cfg_group_copy()
    def cfg_group_copy(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
        new_group: str,
        new_task: str | None = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """复制 Group；``new_task`` 为空时在同一 Task 内复制。"""
        return result

    @modconfig.cfg_group_reset()
    def cfg_group_reset(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """把一个 Group 恢复为模型默认值；动态实例用 ``字段@序号`` 定位。"""
        return result

    @modconfig.cfg_arg_get()
    def cfg_arg_get(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
        arg: str,
        default: Any = None,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """读取一个 Arg 的当前值；失败时 ``events[0].value`` 为 ``default``。"""
        return result

    @modconfig.cfg_arg_set()
    def cfg_arg_set(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
        arg: str,
        value: Any,
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """设置一个 Arg 的值。"""
        return result

    @modconfig.cfg_arg_batch_set()
    def cfg_arg_batch_set(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        events: list[ConfigSetEvent],
        post_edit: bool = False,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """批量设置 Arg 的值。"""
        return result

    @modconfig.cfg_arg_reset()
    def cfg_arg_reset(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        task: str,
        group: str,
        arg: str,
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """把一个 Arg 恢复为模型默认值。"""
        return result

    @modconfig.cfg_arg_batch_reset()
    def cfg_arg_batch_reset(
        self,
        result: tuple[bool, list[ConfigSetEvent]],
        config_name: str,
        events: list[ConfigSetEvent],
    ) -> tuple[bool, list[ConfigSetEvent]]:
        """批量把 Arg 恢复为模型默认值。"""
        return result


class ConfigMod(ConfigAccessState, ConfigModMixin):
    """Worker-side configuration runtime.

    ``ConfigAccessState`` owns mutable cache and persistence state; the mixin
    only supplies the public decorated methods.  Keeping these responsibilities
    separate allows ``ConfigGui`` to use the mixin without this stateful base.
    """

    __entry_info__ = ModEntryInfo.oas()
