"""
Maintenance flows of the backend: restart, update and the daily action

The backend has exactly one flow at a time: ``startup`` / ``restart`` /
``update`` / ``daily``. A flow stops the workers, does its work and either
hands the process over to a new one (a resume file plus a supervisor restart)
or wraps up and releases the backend again. The layers of the package, each
one building on the previous:

- ``restart_base``: the state of the slot (the flow in flight, the frozen
  resume intent) and the context managers that write it. Plain Python
  attributes: the worker manager and the rpc layer read them directly;
- ``restart_step``: the single steps of a flow (stop the workers, apply the
  deploy jobs, hand over, resume the queue of the new process, wrap up);
- ``restart_flow``: the four flow bodies, composing the steps;
- ``restart_manager``: the entries (accept / refuse with a user-facing reason),
  the cancellation windows and ``run()`` -- the lifespan entry that owns the
  nursery the flows are tasks of;
- ``resume_file``: the resume file protocol (the one-shot credential handed
  over through the supervisor) with the ``updated_all_at`` mark that lets the
  new process skip a full update it does not need;
- ``update_check``: the check module of the mods (one ``ModUpdateCheck`` per
  mod: the state of the Update topic, the sequences, the manual checks, the
  pause / restore discipline), deliberately independent of the flows;
- ``daily``: the daily bookkeeping and the task deciding when the daily action
  is due.

This package replaces the job-free orchestration of the removed modules
(``restart_legacy`` / ``restart_context`` / ``update_manager`` / ``update_mod``
/ ``update_startup`` / ``schedule``): every caller moved over, the legacy
modules are gone.

Ported from ``alasio/backend/app/restart`` module by module. Every deviation is
recorded in the docstring of its own module and summarised in
``oas/backend/README.md``.
"""
