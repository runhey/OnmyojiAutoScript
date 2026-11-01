"""
The ConfigScan topic: the local configuration databases of the GUI.

Ported from alasio/backend/topic/scan.py. Two deviations, both recorded
in oas/backend/README.md:

- the default-config creation (``_create_default_config`` /
  ``create_default_config``) is not ported yet: it walks MOD_LOADER,
  which the OAS config entry loader does not expose;
- trio.to_thread.run_sync is anyio.to_thread.run_sync here.
"""

from typing import List

import anyio

from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.source import DiskCache, GlobalSource
from oas.backend.ws.ws_topic import BaseTopic
from oas.config.table.scan import ConfigInfo, DndRequest, ScanTable


class ConfigScanSource(GlobalSource, DiskCache):
    """
    Config scan disk-cache source, resident (GC=False).

    Its data is read lock-free by other modules and sources (a rebuilt
    instance would read empty), so it never enters the data-expiry gc:
    the GC switch is the only difference from a regular DiskCache -- the
    TTL stays as the fetch freshness window (how long reinit may skip a
    re-read of the disk).
    """

    TOPIC_NAME = 'ConfigScan'
    # GC=False keeps the instance resident: readers assume a stable
    # populated instance, never recycle it. TTL (model default 8s) stays
    # as the fetch freshness window.
    GC = False
    data: 'dict[str, ConfigInfo]'

    def on_init(self):
        table = ScanTable()
        return table.scan()


class ConfigScan(BaseTopic):
    TOPIC_NAME = 'ConfigScan'

    async def get_source(self):
        """
        Data preparation: refresh the scan cache (no-op when fresh), the
        snapshot is returned by source.subscribe().
        """
        source = ConfigScanSource()
        await source.reinit()
        return source

    @rpc
    async def config_add(self, name: str, mod: str):
        """
        Create a new config file.

        Args:
            name (str): Config name
            mod (str): Module name
        """
        # Run the synchronous ScanTable.config_add in a thread
        scan_table = ScanTable()
        await anyio.to_thread.run_sync(scan_table.config_add, name, mod)

        # Force rescan to update the data and notify observers
        await ConfigScanSource().reinit(force=True)

    @rpc
    async def config_copy(self, old_name: str, new_name: str):
        """
        Copy an existing config as a new config.

        Args:
            old_name (str): Source config name
            new_name (str): Target config name
        """
        # Run the synchronous ScanTable.config_copy in a thread
        scan_table = ScanTable()
        await anyio.to_thread.run_sync(scan_table.config_copy, old_name, new_name)

        # Force rescan to update the data and notify observers
        await ConfigScanSource().reinit(force=True)

    @rpc
    async def config_rename(self, old_name: str, new_name: str):
        """
        Rename an existing config.

        Args:
            old_name (str): Source config name
            new_name (str): Target config name
        """
        # Run the synchronous ScanTable.config_rename in a thread
        scan_table = ScanTable()
        await anyio.to_thread.run_sync(scan_table.config_rename, old_name, new_name)

        # Force rescan to update the data and notify observers
        await ConfigScanSource().reinit(force=True)

    @rpc
    async def config_del(self, name: str):
        """
        Delete a config file.

        Args:
            name (str): Config name to delete
        """
        # Run the synchronous ScanTable.config_del in a thread
        scan_table = ScanTable()
        await anyio.to_thread.run_sync(scan_table.config_del, name)

        # Force rescan to update the data and notify observers
        await ConfigScanSource().reinit(force=True)

    @rpc
    async def config_dnd(self, configs: List[DndRequest]):
        """
        Drag and drop configs.
        Requests will be treated as instructions that where would the user like to insert this config onto.
        ScanTable will re-sort all configs based on user's request.

        Args:
            configs (List[DndRequest]): List of drag and drop requests
        """
        # Run the synchronous ScanTable.config_dnd in a thread
        scan_table = ScanTable()
        await anyio.to_thread.run_sync(scan_table.config_dnd, configs)

        # Force rescan to update the data and notify observers
        await ConfigScanSource().reinit(force=True)
