"""Application-level shared base of the config GUI view sources.

Ported from ``alasio/backend/topic/_gui_config.py`` (178 lines). The body is
upstream apart from three deviations:

- the import rewrites (``alasio.`` -> ``oas.``, ``trio`` -> ``anyio``);
  ``MOD_LOADER`` now comes from ``oas.mod.loader.ModLoader``;
- the full view is read through the Mod facade directly
  (``MenuModMixin.menu_scheme_get`` + ``ConfigModMixin.config_read``) instead
  of upstream's GUI projection entry point (``get_gui_config``): OAS dropped
  that projection layer, so the view below is the raw
  ``{task: {group: {arg: value}}}`` mapping ``config_read`` returns. The data
  does not have to match Alasio, only the event routing does;
- the registry below collects no class today. Upstream registers
  ``ConfigArgSource`` / ``DashboardSource`` here, the two concrete subclasses
  that built their views through this base; the OAS topics
  (``topic/config.py``) read the same facade directly from their own
  ``KeyedSource`` and refresh it after a write instead, so nothing subclasses
  this base yet. ``DashboardSource`` (upstream ``backend/topic/dashboard.py``,
  38 lines) is not ported either.

The TaskQueue half of ``backend/topic/_config_event.py`` still has no source
(``topic/que.py``, 703 lines, is not ported).
"""

import anyio

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import NoCachePush
from oas.backend.topic.scan import ConfigScanSource
from oas.mod.loader import MOD_LOADER
from oas.config.entry.model import ConfigSetEvent, ModelConfigRef
from oas.ext.deep import deep_iter

# Concrete GUI view source classes that take part in config-save routing.
# Collected at class definition time (only real topics -- with a
# TOPIC_NAME -- register, see GuiConfigSource.__init_subclass__).
_CONFIG_GUI_CLASSES: 'list[type]' = []


class GuiConfigSource(NoCachePush):
    """
    Application-level shared base of the config GUI view sources
    (ConfigArgSource / DashboardSource). It is NOT a framework dimension:
    it is the one place where the "config view over ConfigSetEvent" shape
    lives, so the framework base (NoCachePush) stays generic.

    Both views are built from the same blocks:
    - the full view is the raw ``config_read`` mapping of the tasks of
      the nav (``{task: {group: {arg: value}}}``); the nav name only
      selects which tasks are read, so an unknown nav yields an empty
      view;
    - the event -> keyed-set mapping is projected from that SAME view:
      every displayed argument is keyed by the triple the events carry
      (task, group, arg), which is also its location in the view, so an
      event patches the displayed value in place -- no separate
      structure to keep in sync. Both are built together on the first
      subscribe (_build_full, in a thread); the mapping is empty ({})
      before that -- empty mapping drops every event, which is safe
      because events only reach registered subscribers and registration
      happens after the build.
    - both consume ConfigSetEvent (or its dict form, as decoded from
      worker bytes) and convert it into a keyed 'set' patch of the
      displayed value.

    Subclasses only fix their key shape / constructor arguments and the
    nav name: ConfigArgSource(mod, config, nav, lang) for any nav, or
    DashboardSource(mod, config, lang) with nav fixed to 'dashboard'.
    The registry (KeyedSource.get) converts a KeyError of the constructor
    (config / mod deleted or the config re-bound to another mod) into
    None. A deleted / unknown nav is NOT validated in the constructor:
    the scheme lookup of the build raises KeyError, which build turns into
    an empty view at subscribe time (silent no-data, same visible result
    as "no source").
    """

    def __init__(self, mod_name, config_name, nav_name, lang):
        super().__init__()
        self.mod_name = mod_name
        self.config_name = config_name
        self.nav_name = nav_name
        self.lang = lang
        # In-memory existence check only, no IO (see the class docstring):
        # config deleted / re-bound or mod deleted => KeyError, and
        # KeyedSource.get() converts that into None (no source).
        self._validate_config()
        # Event -> keyed-set mapping. Projected from the full view on the
        # first subscribe (_build_full); empty until then (an empty
        # mapping drops every event -- safe, see the class docstring).
        self.dict_config_to_topic = {}

    def _validate_config(self):
        """
        In-memory existence check of the view: the config must be present
        in the current scan data and bound to this mod; the mod itself
        must exist. Deliberately does NOT touch the disk / nav structure:
        a missing nav surfaces as an empty view at subscribe time (the
        scheme lookup of the build yields {}).

        Raises:
            KeyError: When the config or mod no longer exists, or the
                config was re-bound to another mod.
        """
        configs = ConfigScanSource().data
        try:
            info = configs[self.config_name]
        except KeyError:
            raise KeyError(f'No such config: "{self.config_name}"') from None
        if info.mod != self.mod_name:
            # the config was re-bound to another mod (external edit):
            # treat it as nonexistent under this key
            raise KeyError(
                f'Config "{self.config_name}" is not under mod "{self.mod_name}"'
            ) from None
        try:
            MOD_LOADER.dict_mod[info.mod]
        except KeyError:
            raise KeyError(f'No such mod: "{info.mod}"') from None

    def build(self):
        """
        Read the view of this nav and project the event mapping from it.

        Returns:
            tuple[dict, dict]: The full view (``{task: {group: {arg: value}}}``,
            falsy when the nav or the config is gone) and the event mapping
            (``{(task, group, arg): (task, group, arg)}``).
        """
        view = self._read_view()
        # the view is keyed by the triple the events carry, so every
        # displayed argument maps to its own location: an event patches the
        # displayed value in place
        mapping = {}
        for keys, _ in deep_iter(view, depth=3):
            task, group, arg = keys
            mapping[(task, group, arg)] = (task, group, arg)
        return view, mapping

    def _read_view(self):
        """
        Read the tasks of this nav through the Mod facade.

        The scheme only selects the tasks; every group of a selected task is
        read completely (the ``ref.task`` form, with ``ref.group`` empty). An
        unknown / deleted nav makes ``menu_scheme_get`` raise KeyError, which
        is the empty view here -- the same visible result as the empty view of
        the upstream projection.

        Returns:
            dict: ``{task: {group: {arg: value}}}``, empty when the nav is
            gone.
        """
        try:
            scheme = MOD_LOADER.menu_scheme_get(self.config_name, self.nav_name)
        except KeyError:
            return {}
        tasks = []
        for group in scheme.get('groups', {}).values():
            if isinstance(group, dict):
                tasks.extend(
                    task for task in group.get('tasks', ()) if isinstance(task, str)
                )
        return MOD_LOADER.config_read(
            self.config_name,
            ModelConfigRef(task=list(dict.fromkeys(tasks)), group=[]),
        )

    async def _build_full(self):
        """
        [Trio] Build the full view AND the event mapping in one thread
        round trip (file reads must not block the event loop). The
        mapping is projected from the same view the full is built from,
        so it is always consistent with the full -- no separate structure
        read, no loader filter rules to replicate (every view row carries
        its (task, group, arg) reference; rows without a resolvable
        reference never enter the view).

        The mapping is assigned before any subscriber is registered
        (subscribe registers after _get_payload completes), so the event
        forwarding readers (_convert, any thread) always see the finished
        mapping -- the write needs no lock. Single-flight serializes the
        side effect to exactly once per instance: concurrent subscribers
        of the same key wait for the running build and reuse its payload,
        they never re-run the builder.

        An empty view (unknown nav: the scheme lookup fails; unknown or
        deleted config: config_read yields nothing) yields an empty
        mapping; the falsy view makes subscribe register without a full
        event (empty-view semantics).

        Returns:
            dict: The full view data (falsy = empty view).
        """
        view, mapping = await anyio.to_thread.run_sync(self.build)
        self.dict_config_to_topic = mapping
        return view

    def _convert(self, event):
        """
        [锁内] One config-save event -> a set response of the view key, or
        None when the arg is not displayed by this view (dropped).
        """
        # we may receive dict from worker, because it's decoded from bytes
        if type(event) is dict:
            event = ConfigSetEvent(**event)

        key = self.dict_config_to_topic.get((event.task, event.group, event.arg))
        if key is None:
            # not displaying this key
            return None
        # the key is the (task, group, arg) location of the displayed value
        return ResponseEvent(t=self.TOPIC_NAME, o='set', k=key, v=event.value)

    # ---------------- config-save routing (application layer) ----------------

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # a concrete view source (real topic) joins the config-save route
        # list once at class definition time
        if cls.TOPIC_NAME:
            _CONFIG_GUI_CLASSES.append(cls)

    @classmethod
    def dispatch_config(cls, config_name, event):
        """
        [任意线程] Route a config-save event to every GUI view source of
        the config (every nav instance of ConfigArg + the Dashboard
        source). Each source filters the event by its own mapping (inbox +
        doorbell under its lock). Thread safe: instance enumeration goes
        through a locked registry snapshot; sources removed in between
        drop the event (no subscriber).
        """
        for src_cls in _CONFIG_GUI_CLASSES:
            for _, source in src_cls.singleton_items():
                if source.config_name == config_name:
                    source.on_event(event)
