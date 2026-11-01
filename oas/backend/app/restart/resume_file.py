"""
Ported verbatim from ``alasio/backend/app/restart/resume_file.py``.

Deviations from upstream:

- the import rewrites: ``alasio.`` -> ``oas.`` on the five ``alasio`` import
  lines (``oas.backend.mpipe.mpipe_backend``, ``oas.ext.env``,
  ``oas.ext.path``, ``oas.ext.path.atomic``, ``oas.logger``) and on the
  ``alasio.backend.app.restart_context`` module path named in the docstring
  below;
- trio -> anyio, in code only: ``import trio`` -> ``import anyio``,
  ``trio.Lock()`` -> ``anyio.Lock()`` and ``trio.to_thread.run_sync`` ->
  ``anyio.to_thread.run_sync`` (two calls; the anyio thread hop is
  non-abandoning by default, like the trio call it replaces). No other trio
  construct appears in the file: no Event / move_on_after / fail_after /
  CancelScope / doorbell;
- the ``trio`` wording of the upstream comments and docstrings is left intact,
  as the port rules keep prose unchanged; no ``alasio_lang``, ``alasio_token``
  or ``Alasio`` spelling occurs upstream, so none is renamed (the
  ``ALASIO_RESUME_TOKEN`` environment variable name is kept as upstream: only
  the exact ``alasio_token`` spelling is in the rename map, and no OAS-side
  supervisor consumes it yet).
"""

"""
Resume file protocol of the graceful backend restart

The old backend writes the resume intent to a file and announces its one-shot
credential to the supervisor; the new backend receives the credential through
the environment and consumes the file. This module owns the file IO only (the runtime state of a flow lives in
``manager``): migrated from the removed legacy orchestration
(``oas.backend.app.restart_context``) with the ``updated_all_at`` field of
the four-flow model.

File protocol:
- path: <PROJECT_ROOT>/log/resume/resume-{token}.json, token = random hex;
- content: the payload itself, {"ts", "owner", "configs", "actions",
  "updated_all_at"}; written once, after the workers stopped (never during the
  wait);
- the folder may hold the files of other backends as well: a transaction only
  ever touches the file named by its own token (write / read-and-delete /
  defensive withdraw), it never deletes or rewrites a foreign file; leftovers
  of dead sessions are removed by cleanup() (age based) only;
- credential: f'{token}-{checksum}' with checksum = HMAC-SHA256(token, payload);
  the checksum is NOT stored in the file, so a file whose credential was never
  announced is never consumed (the read requires the token from the
  credential);
- the file is read at most once and always deleted right after the read;
- the publication and the withdrawal are two critical sections of one lock
  held by the tasks (ResumeFiles._publication_lock): the publication writes the
  file AND announces its credential, the withdrawal removes the file AND
  retracts the credential (announces an empty one; the supervisor slot is
  latest-wins). The lock is held by the task around the pool hop, not by the
  pool thread, so trio orders the two by itself: a flow cancelled while it
  waits for the section is cancelled at the lock acquire (a checkpoint) and
  publishes nothing, and one cancelled while the section is held leaves its
  file and credential to the withdrawal, which waits for the section and
  retracts the credential last. A cancelled flow therefore leaves no file
  behind, and a file whose removal failed is inert: "no credential announced
  => the file is never read" holds again, because the credential the write may
  have announced was taken back.

Credential handover (same session): the old backend announces the credential
with command:resume:<credential>; the supervisor stores it and injects it into
the next spawned backend as ALASIO_RESUME_TOKEN, then clears it once the new
backend announced startup completion (command:started). An empty credential is
the retraction: the stored slot is cleared and nothing is injected any more.
"""

import hashlib
import hmac
import os
import secrets
import time
from typing import List, Optional

import anyio
import msgspec

from oas.backend.mpipe.mpipe_backend import mpipe_backend
from oas.ext import env
from oas.ext.path import PathStr
from oas.ext.path.atomic import atomic_read_bytes, atomic_remove, atomic_write
from oas.logger import logger

# Age of a resume file that counts as a stale leftover: nothing stale can be
# consumed (a read requires the one-shot credential), this only keeps the disk
# clean after a session was killed before its transaction finished
RESUME_CLEANUP_AGE = 3 * 24 * 3600.0
# Environment variable the supervisor injects into the new backend
RESUME_TOKEN_ENV = 'ALASIO_RESUME_TOKEN'
# Resume file name prefix / suffix (resume-{token}.json)
RESUME_FILE_PREFIX = 'resume-'
RESUME_FILE_SUFFIX = '.json'
# Owner of a resume file: the restart flows write 'restart' (the legacy update
# transaction writes 'update' until it is replaced by the update flow)
OWNER_RESTART = 'restart'
OWNER_UPDATE = 'update'


class ResumeRecord(msgspec.Struct):
    """
    Resume file payload: the configs to auto-resume after a graceful backend
    restart, plus optional actions the new backend runs before the resume.
    """

    # unix timestamp of the write
    ts: float
    # transaction owner: 'restart' or 'update'
    owner: str
    # config names to auto-resume
    configs: List[str]
    # built-in action tags (no shell) executed before the resume
    actions: List[str]
    # Completion time of the last full update the writer ran, 0 when it ran
    # none: the new backend skips its startup full update when it is set (the
    # process it replaces just checked and applied every mod), so a daily
    # restart does not check everything twice. Optional for the records written
    # by the legacy orchestration (decoded as 0)
    updated_all_at: float = 0.0


class ResumeFiles:
    """
    Resume file IO of one backend process: path, credential, write / read /
    withdraw / cleanup, and the publication slot of the file this process wrote
    """

    def __init__(self, folder: 'Optional[PathStr]' = None):
        """
        Args:
            folder (PathStr): Folder holding the resume files; None resolves
                <PROJECT_ROOT>/log/resume on every call (PROJECT_ROOT is bound
                once per process at the backend startup, the lazy resolution
                only serves the tests)
        """
        self._folder = folder
        # critical sections of the resume publication, held by the tasks (not
        # by the pool threads): write() writes the file and announces the
        # credential inside it, withdraw() removes the file and retracts the
        # credential inside it. A flow that only waits for the section is
        # cancelled at the acquire (a checkpoint), so a cancelled flow
        # publishes nothing; one that holds the section is left to run to
        # completion and is withdrawn afterwards
        self._publication_lock = anyio.Lock()
        # the file this process published (withdraw() removes it and retracts
        # its credential), None when nothing was published yet
        self.file: 'Optional[PathStr]' = None
        # owner of the published file
        self.owner = ''

    def reset(self):
        """
        Drop the publication slot (tests: a fresh process has a fresh slot)
        """
        self.file = None
        self.owner = ''

    @property
    def folder(self) -> PathStr:
        """
        Folder holding the resume files (shared by every backend of a project)

        Returns:
            PathStr: <PROJECT_ROOT>/log/resume
        """
        if self._folder is not None:
            return self._folder
        return env.PROJECT_ROOT.joinpath('log/resume')

    def file_of(self, token: str) -> PathStr:
        """
        Path of the resume file of one token

        The `file` attribute holds the file THIS process wrote; this method
        resolves where the file of any token lives (token is the isolation,
        the file name carries it).

        Args:
            token (str): One-shot random token

        Returns:
            PathStr: <PROJECT_ROOT>/log/resume/resume-{token}.json
        """
        return self.folder.joinpath(f'{RESUME_FILE_PREFIX}{token}{RESUME_FILE_SUFFIX}')

    def checksum(self, token: str, payload: bytes) -> str:
        """
        HMAC-SHA256 of the payload under the token (the credential's judge)

        Args:
            token (str): One-shot random token
            payload (bytes): Exact bytes written to / read from the resume file

        Returns:
            str: Hex digest
        """
        return hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()

    def iter_files(self) -> 'List[PathStr]':
        """
        Existing resume files (empty when the folder or the file list is missing)

        Returns:
            List[PathStr]: Full paths of the resume-*.json files
        """
        folder = self.folder
        try:
            entries = list(folder.iter_entry())
        except FileNotFoundError, NotADirectoryError, OSError:
            return []
        files = []
        for entry in entries:
            try:
                name = entry.name
                if not (
                    name.startswith(RESUME_FILE_PREFIX)
                    and name.endswith(RESUME_FILE_SUFFIX)
                ):
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue
            files.append(folder.joinpath(name))
        return files

    async def write(
        self, configs, owner=OWNER_RESTART, actions=None, updated_all_at=0.0
    ) -> str:
        """
        Publish the resume intent: write the file and announce its credential

        The publication section of this process: async, with the blocking work
        (disk write + supervisor pipe) in the trio thread pool, so the event
        loop stays responsive.

        Called once per handover, after the workers stopped (never during the
        wait): the content is the final resume list, there is no intermediate
        write and no rewrite. The file hits the disk and the credential is
        announced inside the section, so the file exists before the supervisor
        can hand the credential to the next backend ("no credential announced
        => the file is never read"), a call site cannot forget the announce,
        and no cancel can interleave between the file and its credential. The
        lock is held by this task: a flow cancelled while this call waits for
        the section is cancelled at the acquire (a checkpoint) and publishes
        nothing, and one cancelled while the section is held leaves the file
        and the credential to the withdrawal, which waits for the section and
        retracts the credential afterwards. Only the file of this process is
        written: other resume files in the folder (another backend, a session
        that died before its transaction finished) are left untouched -- they
        can never be consumed without their own credential, and the stale ones
        are removed by cleanup().

        Args:
            configs (list[str]): Configs to auto-resume after the restart
            owner (str): Writer owner, OWNER_RESTART ('restart') or
                OWNER_UPDATE ('update')
            actions (list[str]): Optional action tags the new backend runs
                before the resume
            updated_all_at (float): Completion time of the last full update of
                the writer, 0 when it ran none

        Returns:
            str: Credential string f'{token}-{checksum}', already announced to
                the supervisor
        """
        async with self._publication_lock:
            file, credential = await anyio.to_thread.run_sync(
                self._write_and_announce,
                list(configs),
                owner,
                list(actions) if actions else [],
                updated_all_at,
            )
            # the slot belongs to the trio thread; the section stays held until
            # the withdrawal can see what this call published
            self.file = file
            self.owner = owner
        return credential

    def _write_and_announce(self, configs, owner, actions, updated_all_at):
        """
        Write the resume file and announce its credential (blocking, pool only)

        Called inside the publication section: the file and its credential are
        one step and are never separated by a cancel.

        Args:
            configs (list[str]): Configs to auto-resume after the restart
            owner (str): Writer owner
            actions (list[str]): Action tags
            updated_all_at (float): Completion time of the last full update

        Returns:
            tuple[PathStr, str]: The written file and its credential
        """
        token = secrets.token_hex(16)
        record = ResumeRecord(
            ts=time.time(),
            owner=owner,
            configs=configs,
            actions=actions,
            updated_all_at=updated_all_at,
        )
        payload = msgspec.json.encode(record)
        credential = f'{token}-{self.checksum(token, payload)}'
        file = self.file_of(token)
        atomic_write(file, payload)
        # the write is complete before the credential leaves this method: the
        # supervisor only ever learns about a file that is already on disk
        self.announce(credential)
        logger.info(
            f'[Restart] Resume file written: {file} '
            f'(owner={owner}, {len(configs)} configs, {len(actions)} actions, '
            f'updated_all_at={updated_all_at:.0f})'
        )
        return file, credential

    async def withdraw(self):
        """
        Withdraw this process' publication: remove the file, retract its
        credential

        The mirror of write(), in the same critical section: the publication
        writes the file and announces the credential, the withdrawal removes
        the file and announces '' (the supervisor slot is latest-wins, so the
        empty announcement takes the credential back). The lock is held by the
        task, so a publication in flight is left to run to completion first,
        and a publication still waiting for the section never happens at all
        (its task is cancelled at the acquire): whatever the timing, the
        retraction is the last word the supervisor hears about this process,
        and a file whose removal failed is inert from then on. The blocking
        work (the removal and the pipe send) runs in the trio thread pool,
        inside the section.

        Called by the cancel path of the update flow and by the failed handover
        (the process is not replaced, nothing may consume the file), inside a
        shielded scope: a cancel must complete. An idle withdrawal is a no-op:
        only the file this process published is removed, a foreign file in the
        folder is never touched.

        Returns:
            PathStr | None: The removed file, None when there was nothing to
                remove (nothing published)
        """
        async with self._publication_lock:
            file = self.file
            if file is None:
                # nothing of this process to withdraw: no file of ours to
                # remove and no credential of ours to retract
                return None
            self.file = None
            self.owner = ''
            removed = await anyio.to_thread.run_sync(self._remove_and_retract, file)
        if not removed:
            return None
        logger.info(f'[Restart] Resume file removed by the withdraw: {file}')
        return file

    def _remove_and_retract(self, file):
        """
        Remove the resume file and retract its credential (blocking, pool only)

        Called inside the withdrawal section, after the file was taken out of
        the slot.

        Args:
            file (PathStr): The file published by this process

        Returns:
            bool: True when the file was removed
        """
        try:
            removed = atomic_remove(file)
        except OSError as e:
            logger.warning(f'[Restart] Failed to remove the resume file {file}: {e}')
            removed = False
        # the retraction is announced after the removal (failed or not) and
        # always after the announcement the write made in the same section: the
        # supervisor only keeps this empty credential from now on
        self.announce('')
        return removed

    def read(self) -> 'Optional[ResumeRecord]':
        """
        Consume the resume file of this backend (new process startup)

        The credential comes from the supervisor (ALASIO_RESUME_TOKEN). Without
        a credential nothing is read, so a file left behind by a killed session
        can never be consumed. With a credential the file named by its token is
        read and deleted immediately -- a file never survives a read, whatever
        the verification result -- then the payload is verified against the
        checksum. A file that cannot be read at all is removed best effort too,
        except when the read was denied by permissions (the denial is taken as
        covering the removal): the one-shot credential has no holder left, so
        nobody can ever consume the file again.

        Returns:
            ResumeRecord | None: The verified record, or None (no credential,
                no file, checksum mismatch, malformed payload)
        """
        credential = os.environ.get(RESUME_TOKEN_ENV, '')
        if not credential:
            return None
        token, sep, checksum = credential.partition('-')
        if not (sep and token and checksum):
            logger.warning('[Restart] Resume file not read: malformed credential')
            return None
        file = self.file_of(token)
        payload = self._read_file(file)
        if payload is None:
            return None
        actual = self.checksum(token, payload)
        if not hmac.compare_digest(actual, checksum):
            logger.warning(
                '[Restart] Resume file dropped: checksum mismatch (tampered or corrupted)'
            )
            return None
        try:
            record = msgspec.json.decode(payload, type=ResumeRecord)
        except msgspec.ValidationError as e:
            logger.warning(f'[Restart] Resume file dropped: invalid payload: {e}')
            return None
        return record

    def _read_file(self, file):
        """
        Read the resume file, delete it, and return its payload

        The read and the deletion are one step (read-once): a file that was
        read never survives, whatever the verification result of its payload. A
        file whose read failed is removed by the same call below -- this read
        was the only holder of the one-shot credential, so nobody can ever
        consume it again. The deletion is best effort: a failure only logs and
        leaves the file to the 3 day stale cleanup, the payload (when there is
        one) is returned all the same. Two failures return early: a missing
        file has nothing to delete, and a permission denial is taken as
        covering the removal as well (no attempt, and no retry loop on
        Windows).

        Args:
            file (PathStr): The file named by the credential

        Returns:
            bytes | None: The payload, or None (missing or unreadable)
        """
        try:
            payload = atomic_read_bytes(file)
        except FileNotFoundError:
            logger.info(f'[Restart] Resume file not found: {file}')
            return None
        except PermissionError as e:
            logger.warning(f'[Restart] Resume file not readable: {file}: {e}')
            # the denial is taken as covering the removal too: no attempt (and
            # no retry loop on Windows), the stale cleanup takes it
            return None
        except OSError as e:
            logger.warning(f'[Restart] Resume file not readable: {file}: {e}')
            # fall through to the removal below: this read was the only holder
            # of the one-shot credential, so the file can never be consumed any
            # more and must not linger for the 3 day stale cleanup
            payload = None
        # read once: the file never survives a read, valid or not (an unreadable
        # file falls through to the same removal; a missing file and a
        # permission denial returned early above)
        try:
            atomic_remove(file)
        except OSError as e:
            # best effort: a failed removal only leaves the file to the 3 day
            # stale cleanup, the payload is returned all the same
            logger.warning(f'[Restart] Failed to remove the resume file {file}: {e}')
        return payload

    def cleanup(self):
        """
        Remove stale resume files (process startup, best effort)

        Deletes resume files older than RESUME_CLEANUP_AGE. Nothing stale can
        be consumed anyway (a read requires the one-shot credential); this only
        keeps the disk clean when a process was killed before its transaction
        finished (the normal path is deleted by the read itself). Never raises:
        a cleanup problem must not block the backend startup.
        """
        try:
            files = self.iter_files()
        except Exception as e:
            logger.warning(f'[Restart] Resume cleanup failed: {e}')
            return
        now = time.time()
        removed = 0
        kept = 0
        for file in files:
            try:
                st = file.stat()
            except FileNotFoundError, OSError:
                continue
            if now - st.st_mtime > RESUME_CLEANUP_AGE:
                try:
                    if atomic_remove(file):
                        removed += 1
                except OSError as e:
                    logger.warning(
                        f'[Restart] Failed to remove stale resume file {file}: {e}'
                    )
                continue
            kept += 1
        if removed or kept:
            logger.info(
                f'[Restart] Resume cleanup: removed {removed} stale files, kept {kept}'
            )

    def announce(self, credential: str):
        """
        Announce (or retract) the resume credential over the supervisor pipe

        Called by write() right after the file hit the disk and by withdraw()
        for its retraction (blocking: the pipe send runs in the caller's thread
        pool hop).

        Sends b'command:resume:<credential>'; the supervisor stores the latest
        announcement and injects it into the next spawned backend
        (ALASIO_RESUME_TOKEN). An empty credential is the retraction: the
        stored slot is cleared and nothing is injected any more, so a cancelled
        flow cannot be consumed whatever the state of its file. Without a
        supervisor the message is silently dropped (send default), so a file
        written without a supervisor is never consumed: the credential cannot
        be handed over.

        Args:
            credential (str): Credential string returned by write(), or '' to
                retract the announced one
        """
        # the file exists before the credential leaves this method, and the
        # withdraw announces the retraction after the write (the publication
        # section orders the two): the invariant "no credential announced =>
        # the file is never read" holds in both directions
        mpipe_backend.send(b'command:resume:' + credential.encode())
        if credential:
            logger.info('[Restart] Resume credential announced to the supervisor')
        else:
            logger.info('[Restart] Resume credential retracted from the supervisor')


# The process-wide resume file IO, used by the flows and the startup of the new
# backend
RESUME_FILES = ResumeFiles()
