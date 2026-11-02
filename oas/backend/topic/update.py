"""
Update topic: the update state of every mod (data = dict[mod_name,
UpdateInfo]), produced by the update check module and update flow.

The source is resident and runtime-produced: a frontend subscription gets the
current in-memory snapshot, then receives incremental changes. OAS currently
has an API-compatible empty update-check implementation, so no mod state is
published and this topic remains empty until the deploy/update producers are
ported.

The state pipeline of one mod:

    checking -> uptodate / available -> queued -> stopping -> downloading -> updating
"""
from typing import Dict

from msgspec import Struct

from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.event import ResponseEvent, RpcValueError
from oas.backend.reactive.source import GlobalSource, ResidentCache
from oas.backend.ws.ws_topic import BaseTopic

# States of a mod update. These names are consumed by the frontend and by the
# update-check / restart flow modules.
UPDATE_STATE = [
    'unmanaged', 'no-supervisor', 'disabled', 'idle', 'checking', 'uptodate',
    'available', 'queued', 'stopping', 'downloading', 'updating',
    'restart-required', 'error',
]


class UpdateInfo(Struct):
    """Update state of one mod, the value stored in the Update topic."""

    state: str
    current_version: str = ''
    latest_version: str = ''
    checked_at: int = 0
    error: str = ''


class UpdateSource(GlobalSource, ResidentCache):
    """Resident update states keyed by mod name.

    Event protocol: ``(mod_name, info | None)``; None deletes that mod's
    entry, otherwise it replaces the entry.
    """

    TOPIC_NAME = 'Update'
    data: 'Dict[str, UpdateInfo]'

    def _apply(self, event):
        name, info = event
        if info is None:
            if name not in self.data:
                return False
            del self.data[name]
            return True
        if self.data.get(name) is info:
            return False
        self.data[name] = info
        return True

    def _convert(self, event):
        name, info = event
        if info is None:
            return ResponseEvent(t=self.TOPIC_NAME, o='del', k=(name,))
        return ResponseEvent(t=self.TOPIC_NAME, o='set', k=(name,), v=info)


class Update(BaseTopic):
    TOPIC_NAME = 'Update'

    async def get_source(self):
        # Update state is event-driven; the current OAS producer publishes
        # nothing yet, so subscribers receive an empty topic.
        return UpdateSource()

    @rpc
    async def update_check(self, name: str):
        """Request an immediate update check for one mod."""
        from oas.backend.app.restart.update_check import UPDATE_CHECK

        try:
            return await UPDATE_CHECK.update_check(name)
        except ValueError as e:
            raise RpcValueError(str(e)) from None

    @rpc
    async def cancel_check(self, name: str):
        """Cancel an in-flight check for one mod, if there is one."""
        from oas.backend.app.restart.update_check import UPDATE_CHECK

        if not UPDATE_CHECK.cancel_check(name):
            raise RpcValueError(f'No check is in flight: "{name}"')

    @rpc
    async def update_apply(self):
        """Start applying available updates as a background maintenance flow."""
        from oas.backend.app.restart.restart_manager import RESTART_MANAGER, FlowRefused
        from oas.backend.app.restart.update_check import UPDATE_CHECK

        if not UPDATE_CHECK.available():
            raise RpcValueError('No update available')
        try:
            RESTART_MANAGER.update_apply()
        except FlowRefused as e:
            raise RpcValueError(str(e)) from None

    @rpc
    async def cancel_apply(self):
        """Cancel the update flow while it is still cancellable."""
        from oas.backend.app.restart.restart_manager import RESTART_MANAGER, FlowRefused

        try:
            await RESTART_MANAGER.cancel_apply()
        except FlowRefused as e:
            raise RpcValueError(str(e)) from None
