"""
The Dashboard topic: the fixed 'dashboard' nav of one config.

Ported from alasio/backend/topic/dashboard.py (38 lines), body apart from the
docstrings and these deviations:

- the full view and the config-save event mapping come from the OAS
  ``GuiConfigSource`` base (``oas/backend/topic/_gui_config.py``), which reads
  the raw ``config_read`` mapping through the Mod facade instead of upstream's
  GUI projection entry point;
- ``DashboardSource`` is the only registrant of that base's config-save routing
  registry in OAS (``ConfigArgSource`` reads the facade directly from its own
  ``KeyedSource``), so a config save reaches this view through the registry;
- OAS menus have no 'dashboard' nav, so the scheme lookup of the build raises
  KeyError and the view of the topic is empty. The framework sends no event for
  an empty snapshot, so a subscriber reads nothing at all (the same silence an
  empty nav shows on a landing page); a mod that adds such a nav publishes its
  view without further changes -- only the set of navs differs from upstream.
"""

from oas.backend.reactive.source import KeyedSource
from oas.backend.topic._gui_config import GuiConfigSource
from oas.backend.topic.state import ConnState
from oas.backend.ws.ws_topic import BaseTopic


class DashboardSource(KeyedSource, GuiConfigSource):
    """
    No-cache view source of the Dashboard topic: key (mod_name, config_name,
    lang), the view is the fixed 'dashboard' nav. The full view and the
    config-save event mapping come from GuiConfigSource; this class only fixes
    its key shape (nav name constant).
    """

    TOPIC_NAME = 'Dashboard'

    def __init__(self, mod_name, config_name, lang):
        super().__init__(mod_name, config_name, 'dashboard', lang)


class Dashboard(BaseTopic):
    """
    The dashboard view of the selected config

    Subscribing registers the view source of the connection's (mod, config,
    lang); the full view is built by ``source.subscribe()`` on registration
    (``NoCachePush``), so ``get_source`` does not reinit.
    """

    TOPIC_NAME = 'Dashboard'

    async def get_source(self):
        """
        Resolve the dashboard source of the current (mod, config, lang); the
        full view is built by source.subscribe() on registration.

        Returns:
            DashboardSource | None: None when the connection has no mod, config
                or language yet, or when the config / mod is gone (silent).
        """
        state = ConnState(self.conn_id, self.server)
        mod_name = await state.mod_name
        config_name = await state.config_name
        lang = await state.lang
        if not mod_name or not config_name or not lang:
            return None
        source = DashboardSource.get(mod_name, config_name, lang)
        if source is None:
            # config / mod deleted: silent
            return None
        return source
