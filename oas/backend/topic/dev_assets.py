"""
The DevAssetsManager topic: the asset folder tree of one mod, for the dev GUI.

Ported from alasio/backend/topic/dev_assets.py (270 lines). OAS has no assets
manager (upstream ``alasio.assets``: ``AssetsManager`` / ``AssetFolder``, 429
lines of folder scanning, resource tracking and asset generation), so the topic
is empty by construction:

- ``DevAssetsSource._build_full`` describes the selected folder without reading
  it: no sub-folders, no resources, no assets. The response carries the real
  ``mod_name`` / ``mod_path_assets`` / ``path`` of the selection plus the three
  empty containers, which is the upstream ``FolderResponse`` shape with an empty
  tree;
- the resource / asset RPCs (``resource_add_base64``, ``resource_del``,
  ``resource_track``, ``resource_untrack``, ``resource_to_asset``,
  ``asset_add``, ``asset_del``, ``resource_rename``, ``asset_rename``) have no
  folder to operate on and refuse with ``RpcValueError`` instead of pretending
  to write. They land together with the assets manager;
- ``set_mod`` / ``set_path`` keep working: they only move the viewport selection
  (the mod must exist, the path must be a plain relative path), so the frontend
  can browse mods and the (empty) tree follows;
- ``_refresh`` is not ported: upstream calls it after every resource operation to
  republish the folder, and the operations that would call it all refuse above;
- the imports are the OAS ones: ``ModEntryInfo`` (``oas/mod/info.py``) replaces
  the Mod domain object, and the build needs no thread hop (upstream scans the
  disk in ``trio.to_thread.run_sync``);
- the topic IS registered in the /api/ws registry, unlike upstream, which keeps
  ``DevAssetsManager`` commented out of it (a dev-only tool). Registering it
  makes the (empty) topic reachable; the resource RPCs stay inert.
"""

from msgspec import Struct

from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.event import RpcValueError
from oas.backend.reactive.rx_trio import async_reactive_source
from oas.backend.reactive.source import KeyedSource, NoCachePush
from oas.backend.ws.ws_topic import BaseTopic
from oas.ext import env
from oas.mod.loader import MOD_LOADER

# Every RPC that would operate on the folder of the selection refuses with this:
# the assets manager of upstream is not ported (see the module docstring), so
# there is no folder to add to / delete from / rename in.
ASSETS_NOT_PORTED = 'Dev assets are not ported to OAS: there is no folder to operate on'


class ManagerState(Struct):
    """
    The viewport selection of the topic: the folder the frontend browses.

    Part of the topic's reactive state, so a mutation pushes the new selection
    to the subscribers of the connection.
    """

    mod_name: str = ''
    path: str = ''


def folder_data(mod_name, path):
    """
    Empty folder tree of a selection, in the upstream ``FolderResponse`` shape.

    Args:
        mod_name (str): Mod the folder belongs to
        path (str): Folder path, relative to the mod root

    Returns:
        dict: ``mod_name`` / ``mod_path_assets`` / ``path`` of the selection,
            with ``folders``, ``resources`` and ``assets`` empty. ``path`` is
            relative to the project root when it can be resolved, like
            upstream, otherwise the mod-relative input is kept.
    """
    try:
        entry = MOD_LOADER.dict_mod[mod_name]
    except KeyError:
        entry = None
    path_assets = entry.path_assets if entry is not None else ''
    try:
        relative = entry.root.joinpath(path).relative_to(env.PROJECT_ROOT).as_posix()
    except AttributeError, TypeError, ValueError:
        relative = path
    return {
        'mod_name': mod_name,
        'mod_path_assets': path_assets,
        'path': relative,
        'folders': [],
        'resources': {},
        'assets': {},
    }


class DevAssetsSource(KeyedSource, NoCachePush):
    """
    No-cache view source of the DevAssets topic: key (mod_name, path).

    The folder tree is built on every subscribe and is NOT cached between
    subscriptions: there is no value in keeping a stale tree, every operation
    rescans anyway. The instance is removed when its last subscriber leaves
    (NoCachePush); a refresh after a resource operation only rescans while
    subscribers are attached (reinit is a no-op without them).

    In OAS the build does not read the folder (see the module docstring): it
    describes the selection with an empty tree.
    """

    TOPIC_NAME = 'DevAssetsManager'

    def __init__(self, mod_name, path):
        super().__init__()
        self.mod_name = mod_name
        self.path = path

    async def _build_full(self):
        """
        Build the (empty) folder tree of the selection. Runs in the
        single-flight path of subscribe / in reinit.

        Returns:
            dict: The empty folder tree, see ``folder_data``.
        """
        return folder_data(self.mod_name, self.path)


class DevAssetsManager(BaseTopic):
    """
    The dev asset manager of one mod: the folder the frontend browses

    The viewport selection (mod + path) is reactive state of this connection and
    defaults to the first mod and its assets folder; subscribing registers the
    view source of that folder.
    """

    TOPIC_NAME = 'DevAssetsManager'

    @async_reactive_source
    async def assets_state(self):
        """
        The viewport selection: the first mod and its assets folder by default.

        Returns:
            ManagerState: The selection of this connection.
        """
        state = ManagerState()
        # select first mod
        if not state.mod_name:
            for entry in MOD_LOADER.dict_mod.values():
                state.mod_name = entry.name
                # init path to assets
                state.path = entry.path_assets
                break
        return state

    @rpc
    async def set_mod(self, mod_name: str):
        """
        Set mod_name

        Args:
            mod_name (str): Name of an existing mod
        """
        try:
            entry = MOD_LOADER.dict_mod[mod_name]
        except KeyError:
            raise RpcValueError(f'No such mod: "{mod_name}"') from None

        state: ManagerState = await self.assets_state
        # set mod
        state.mod_name = mod_name
        state.path = entry.path_assets
        await self.assets_state.mutate()

    @rpc
    async def set_path(self, path: str):
        """
        Set path

        Upstream validates the path through its folder manager; without one, the
        path must at least be a plain relative path inside the mod root.

        Args:
            path (str): Folder path relative to the mod root
        """
        if not path:
            raise RpcValueError('Empty path')
        if path.startswith(('/', '\\')) or '..' in path.split('/'):
            raise RpcValueError(f'Invalid path: "{path}"')

        state: ManagerState = await self.assets_state
        state.path = path
        await self.assets_state.mutate()

    @rpc
    async def resource_add_base64(self, source: str, data: str):
        """
        Add a resource from a base64 encoded string.

        Args:
            source (str): Resource file name
            data (str): Resource file data, base64 encoded
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def resource_del(self, names: list[str]):
        """
        Delete resources without tracking their usage.

        Args:
            names (list[str]): Resource file names
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def resource_track(self, names: list[str]):
        """
        Track resources.

        Args:
            names (list[str]): Resource file names
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def resource_untrack(self, names: list[str]):
        """
        Untrack resources.

        Args:
            names (list[str]): Resource file names
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def resource_to_asset(self, names: list[str]):
        """
        Convert resources to assets.

        Args:
            names (list[str]): Resource file names
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def asset_add(self, name: str):
        """
        Create a new empty asset.

        Args:
            name (str): Asset name
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def asset_del(self, names: list[str]):
        """
        Delete assets and their associated template files.

        Args:
            names (list[str]): Asset names
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def resource_rename(self, old_name: str, new_name: str):
        """
        Rename a resource file.

        Args:
            old_name (str): Current resource file name
            new_name (str): New resource file name
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    @rpc
    async def asset_rename(self, old_name: str, new_name: str):
        """
        Rename an asset.

        Args:
            old_name (str): Current asset name
            new_name (str): New asset name
        """
        raise RpcValueError(ASSETS_NOT_PORTED)

    async def get_source(self):
        """
        Resolve the view source of the current (mod, path); the full folder scan
        is done by source.subscribe() on registration (the source holds no
        cached data between subscriptions).

        Returns:
            DevAssetsSource | None: None when the selection is empty.
        """
        state: ManagerState = await self.assets_state
        if not state.mod_name or not state.path:
            return None
        source = DevAssetsSource.get(state.mod_name, state.path)
        if source is None:
            return None
        return source
