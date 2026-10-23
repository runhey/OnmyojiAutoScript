"""Mutable per-instance state used by the configuration runtime."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class ConfigAccessState:
    """Hold the mutable runtime state for one configuration access instance.

    The state is initialized separately from task initialization/loading. It
    contains the database identity, in-memory snapshots, pending changes,
    temporary overrides, and synchronization controls used by the config
    access layer.
    """

    def __init__(self, config_name: str, task: str = '') -> None:
        self.config_name = config_name
        self.task = task

        # Whether configuration rows have been loaded into the local snapshot.
        self._config_cached = False
        # (connection identity, SQLite data_version) for change detection.
        self._data_version: tuple[int, int] = (0, 0)
        # Snapshot of serialized Group data, keyed by (task, group).
        self._dict_row: dict[tuple[str, str], bytes] = {}
        # Validated Group instances, keyed by (task, group).
        self._dict_group: dict[tuple[str, str], Any] = {}
        # Pending changes, keyed by (task, group, arg).
        self._modified: dict[tuple[str, str, str], Any] = {}

        # In-memory overrides take precedence over database values.
        self._override_config: dict[str, dict[str, Any]] = defaultdict(dict)
        self._override_const: dict[str, Any] = {}
        # Original values saved for restoring temporary overrides.
        self._override_prev_config: dict[str, dict[str, Any]] = defaultdict(dict)

        self.auto_save = True
        self._lock = threading.RLock()
        self._local = threading.local()
        self._local.batch_depth = 0

        self.is_template_config = config_name.startswith('template')
        if self.is_template_config:
            self.auto_save = False
