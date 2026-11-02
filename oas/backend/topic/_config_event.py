"""Unified entry of the ConfigArg config-save events.

Ported from ``alasio/backend/topic/_config_event.py`` (30 lines).

Deviation: upstream also forwards every event to the TaskQueue linkage
(``TaskQueueSource(config_name).on_config_event(event)``, which decides whether
the scheduler settings changed and refreshes or marks the source dirty).
``alasio/backend/topic/que.py`` (703 lines) is not ported to OAS yet, so that
half is absent here. When the TaskQueue topic lands, its call belongs directly
after the GUI dispatch below.

One cosmetic difference: upstream documents the two arguments as
``config_name (str):`` / ``event (...):`` with no description, which ruff D417
rejects (the rule is switched on in this repo, and four already-ported files
carry the same inherited warning). The descriptions below are the only wording
added.
"""

from oas.backend.topic._gui_config import GuiConfigSource


def on_config_event(config_name, event):
    """
    [任意线程] Unified entry of ConfigArg config-save events (sync, thread
    safe). Both the worker recv thread and the RPC success path go through
    here -- there is exactly one entry, so no double-checked or missed
    linkage.

    One call covers every potential consumer of the config:
    - the GUI view sources of the config (every nav of ConfigArg + the
      Dashboard source), routed through the application-level
      GuiConfigSource.dispatch_config;
    - the TaskQueue linkage (TaskQueueSource.on_config_event decides
      whether the scheduler settings changed and refreshes / marks dirty).
      NOT PORTED -- see the module docstring.

    Args:
        config_name (str): Name of the configuration database the event
            belongs to; it is the routing key of the GUI view sources.
        event (ConfigSetEvent | list[ConfigSetEvent] | dict | list[dict]):
            One config-save event, a list of them, or their decoded dict
            form (worker bytes carry dicts).
    """
    # 1. GUI view sources: registry snapshot per source class under its
    #    lock, each source filters the event by its own mapping (inbox +
    #    doorbell under its lock)
    GuiConfigSource.dispatch_config(config_name, event)
    # 2. TaskQueue linkage: upstream calls
    #    TaskQueueSource(config_name).on_config_event(event) here; que.py is
    #    not ported yet, so there is no scheduler source to notify.
