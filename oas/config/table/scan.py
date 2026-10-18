"""GUI configuration-file index stored in ``config/gui.db``."""

from __future__ import annotations

import os
import shutil
from copy import deepcopy
from typing import Union

import msgspec

from oas.config.table.base import ConfigDB, GuiDB
from oas.config.table.key import KeyTable
from oas.ext import env
from oas.ext.path.validate import validate_filename


class ConfigFile(msgspec.Struct):
    name: str
    mod: str = ""

    def read_mod_name(self) -> str:
        self.mod = KeyTable(self.name).mod_get()
        return self.mod


def validate_config_name(config_name: str) -> str:
    """Return an error message, or an empty string when the name is valid."""

    try:
        validate_filename(config_name)
    except ValueError as exc:
        return str(exc)
    if config_name.lower() in {"gui", "webapp", ":memory:"}:
        return f'Config name is protected: "{config_name}"'
    if config_name.lower().startswith("template"):
        return f'Config name is protected: "{config_name}"'
    return ""


def iter_local_files() -> list[ConfigFile]:
    folder = env.PROJECT_ROOT / "config"
    if not folder.exists():
        return []
    result = []
    for path in folder.iter_files(ext=".db"):
        name = path.stem
        if not validate_config_name(name):
            result.append(ConfigFile(name=name))
    return result


class DndRequest(msgspec.Struct):
    name: str
    gid: Union[float, int]
    iid: Union[float, int]


class ConfigInfo(msgspec.Struct):
    name: str
    mod: str
    gid: int
    iid: int
    extra: bytes = b"\x80"
    id: int = 0


class ConfigExtra(msgspec.Struct):
    startup: bool = False


class ScanTable(GuiDB):
    """Maintain GUI ordering and metadata for local config databases."""

    TABLE_NAME = "scan"
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL,
        "name" TEXT NOT NULL,
        "mod" TEXT NOT NULL,
        "gid" INTEGER NOT NULL,
        "iid" INTEGER NOT NULL,
        "extra" BLOB NOT NULL,
        PRIMARY KEY ("id"),
        UNIQUE ("name"),
        UNIQUE ("gid", "iid")
    );
    """
    MODEL = ConfigInfo

    def select_rows(self, *, _cursor_=None) -> dict[str, ConfigInfo]:
        rows = self.select(_cursor_=_cursor_, _orderby_=("gid", "iid"))
        return {row.name: row for row in rows}

    @staticmethod
    def resort_configs(configs: dict[str, ConfigInfo]) -> None:
        sorted_rows = sorted(configs.values(), key=lambda row: (row.gid, row.iid))
        last_gid = object()
        gid = iid = 0
        for row in sorted_rows:
            if row.gid != last_gid:
                gid += 1
                iid = 1
                last_gid = row.gid
            else:
                iid += 1
            row.gid, row.iid = gid, iid

    def scan(self) -> dict[str, ConfigInfo]:
        """Synchronize the GUI index with existing local configuration files."""

        local: dict[str, ConfigFile] = {}
        for row in iter_local_files():
            row.read_mod_name()
            if row.mod:
                local[row.name] = row
        record = self.select_rows()
        with self.cursor(lazy=True) as cursor:
            for name in list(record):
                if name not in local:
                    self.delete_row(record.pop(name), _cursor_=cursor)

            new_record = deepcopy(record)
            self.resort_configs(new_record)
            self._update_positions(record, new_record, cursor)
            record = new_record

            gid = max((row.gid for row in record.values()), default=0)
            for name, local_row in local.items():
                if name in record:
                    if record[name].mod != local_row.mod:
                        record[name].mod = local_row.mod
                        self.update_row(record[name], updates="mod", _cursor_=cursor)
                    continue
                gid += 1
                record[name] = ConfigInfo(name, local_row.mod, gid, 1)
                self.insert_row(record[name], _cursor_=cursor)
            cursor.commit()
        return record

    def _update_positions(
        self,
        old_configs: dict[str, ConfigInfo],
        new_configs: dict[str, ConfigInfo],
        cursor,
    ) -> None:
        """Apply position changes without violating the unique position key."""

        pending = []
        positions = {(row.gid, row.iid) for row in old_configs.values()}
        for name, new_row in new_configs.items():
            old_row = old_configs.get(name)
            if old_row is None:
                continue
            old_pos = (old_row.gid, old_row.iid)
            new_pos = (new_row.gid, new_row.iid)
            if old_pos != new_pos:
                pending.append({"row": new_row, "old_pos": old_pos, "new_pos": new_pos})

        if not pending:
            return

        temporary_gid = max(
            max((position[0] for position in positions), default=0),
            len(old_configs),
        ) + 1

        while pending:
            remaining = []
            progress = False
            for update in pending:
                target = update["new_pos"]
                if target in positions:
                    remaining.append(update)
                    continue
                row = update["row"]
                self.update_row(row, updates=("gid", "iid"), _cursor_=cursor)
                positions.remove(update["old_pos"])
                positions.add(target)
                progress = True

            if not remaining:
                return
            if progress:
                pending = remaining
                continue

            update = remaining[0]
            temporary = deepcopy(update["row"])
            temporary.gid = temporary_gid
            temporary.iid = 1
            self.update_row(temporary, updates=("gid", "iid"), _cursor_=cursor)
            positions.remove(update["old_pos"])
            positions.add((temporary_gid, 1))
            update["old_pos"] = (temporary_gid, 1)
            temporary_gid += 1
            pending = remaining

    def config_add(self, name: str, mod: str) -> None:
        error = validate_config_name(name)
        if error:
            raise ValueError(error)
        file = ConfigDB.config_file(name)
        if file.exists():
            raise FileExistsError(file)
        KeyTable(name).mod_set(mod)

    def config_del(self, name: str) -> None:
        error = validate_config_name(name)
        if error:
            raise ValueError(error)
        from oas.db.conn import SQLITE_POOL

        SQLITE_POOL.delete_file(ConfigDB.config_file(name))
        row = self.select_one(name=name)
        if row is not None:
            self.delete_row(row)

    def config_rename(self, old_name: str, new_name: str) -> None:
        for name in (old_name, new_name):
            error = validate_config_name(name)
            if error:
                raise ValueError(error)
        if old_name == new_name:
            raise ValueError("new_name is the same as old_name")
        old_file = ConfigDB.config_file(old_name)
        new_file = ConfigDB.config_file(new_name)
        if not old_file.exists():
            raise FileNotFoundError(old_file)
        if new_file.exists():
            try:
                same_file = os.path.samefile(old_file, new_file)
            except FileNotFoundError:
                same_file = False
            if not same_file:
                raise FileExistsError(new_file)
        from oas.db.conn import SQLITE_POOL

        SQLITE_POOL.rename_file(old_file, new_file)
        row = self.select_one(name=old_name)
        if row is not None:
            row.name = new_name
            self.update_row(row, updates="name")

    def config_copy(self, source: str, target: str) -> None:
        for name in (source, target):
            error = validate_config_name(name)
            if error:
                raise ValueError(error)
        source_file = ConfigDB.config_file(source)
        target_file = ConfigDB.config_file(target)
        if not source_file.exists():
            raise FileNotFoundError(source_file)
        if target_file.exists():
            raise FileExistsError(target_file)
        target_file.uppath().makedirs(exist_ok=True)
        shutil.copy2(source_file, target_file)

    def config_dnd(self, configs: list[DndRequest]) -> None:
        record = self.select_rows()
        new_record = deepcopy(record)
        for request in configs:
            if request.name not in record:
                raise KeyError(f'config name does not exist: {request.name}')
            new_record[request.name].gid = request.gid
            new_record[request.name].iid = request.iid
        self.resort_configs(new_record)
        with self.cursor(lazy=True) as cursor:
            self._update_positions(record, new_record, cursor)
            cursor.commit()


__all__ = [
    "ConfigExtra",
    "ConfigFile",
    "ConfigInfo",
    "DndRequest",
    "ScanTable",
    "iter_local_files",
    "validate_config_name",
]
