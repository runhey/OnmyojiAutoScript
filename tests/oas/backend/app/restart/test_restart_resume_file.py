"""
The resume file protocol of the graceful restart (``resume_file``).

Every test drives its own ``ResumeFiles`` over an explicit tmp folder: the
process-wide singleton points at the real ``log/resume`` directory of the
repository. The supervisor pipe is stubbed, so nothing leaves the test process
and the announcements can be asserted.
"""

import hashlib
import hmac
import os
import time

import pytest

from oas.backend.app.restart import resume_file as resume_file_module
from oas.backend.app.restart.resume_file import (
    OWNER_RESTART,
    OWNER_UPDATE,
    RESUME_CLEANUP_AGE,
    RESUME_FILE_PREFIX,
    RESUME_FILE_SUFFIX,
    RESUME_FILES,
    RESUME_TOKEN_ENV,
    ResumeFiles,
    ResumeRecord,
)
from oas.ext.path import PathStr

pytestmark = pytest.mark.anyio


class _Pipe:
    """A supervisor pipe stub recording what the resume module sends"""

    def __init__(self):
        self.sent = []

    def send(self, data, strict=False):
        self.sent.append(data)


@pytest.fixture
def pipe(monkeypatch):
    """Stub the supervisor pipe of the resume module"""
    pipe = _Pipe()
    monkeypatch.setattr(resume_file_module, 'mpipe_backend', pipe)
    return pipe


@pytest.fixture
def folder(tmp_path):
    """
    Folder of the resume files of the test (never the repository one).

    The path goes in as ``str``: ``PathStr.new`` normalizes a path string (it is
    not an ``os.PathLike`` consumer).
    """
    return PathStr.new(str(tmp_path / 'log' / 'resume'))


@pytest.fixture
def files(folder):
    """A resume file IO of this test, over the tmp folder"""
    return ResumeFiles(folder=folder)


def test_protocol_constants():
    assert RESUME_TOKEN_ENV == 'ALASIO_RESUME_TOKEN'
    assert RESUME_FILE_PREFIX == 'resume-'
    assert RESUME_FILE_SUFFIX == '.json'
    assert OWNER_RESTART == 'restart'
    assert OWNER_UPDATE == 'update'
    assert RESUME_CLEANUP_AGE == 3 * 24 * 3600.0
    assert isinstance(RESUME_FILES, ResumeFiles)


def test_file_of_and_checksum_are_deterministic(files, folder):
    token = 'abc123'
    path = files.file_of(token)
    assert path == folder.joinpath(f'{RESUME_FILE_PREFIX}{token}{RESUME_FILE_SUFFIX}')
    assert path == files.file_of(token)
    assert path.name == f'{RESUME_FILE_PREFIX}{token}{RESUME_FILE_SUFFIX}'
    assert path.startswith(folder)
    # the checksum is the HMAC-SHA256 of the exact bytes under the token, and
    # the credential is not stored in the file
    payload = b'{"ts": 1.0}'
    expected = hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()
    assert files.checksum(token, payload) == expected
    assert files.checksum(token, payload) == files.checksum(token, payload)
    assert files.checksum(token, payload) != files.checksum('other', payload)


def test_a_fresh_publication_slot_is_empty(files, folder):
    assert files.folder == folder
    assert files.file is None
    assert files.owner == ''
    files.file = files.file_of('abc')
    files.owner = OWNER_RESTART
    files.reset()
    assert files.file is None
    assert files.owner == ''


def test_without_a_credential_nothing_is_read(files, monkeypatch):
    """
    A file whose credential was never announced is never consumed: the read
    requires the one-shot token from the environment.
    """
    monkeypatch.delenv(RESUME_TOKEN_ENV, raising=False)
    path = files.file_of('dead')
    path.atomic_write(b'{}')
    assert files.read() is None
    assert path.exists()


@pytest.mark.parametrize('credential', ['token-only', '-checksum', 'token-'])
def test_a_malformed_credential_is_refused(files, monkeypatch, credential):
    monkeypatch.setenv(RESUME_TOKEN_ENV, credential)
    assert files.read() is None


def test_a_missing_file_is_reported(files, monkeypatch):
    monkeypatch.setenv(RESUME_TOKEN_ENV, 'cafebabe-deadbeef')
    assert files.read() is None


async def test_write_then_read_round_trip(files, pipe, monkeypatch):
    credential = await files.write(
        ['config-a', 'config-b'],
        owner=OWNER_RESTART,
        actions=['cleanup'],
        updated_all_at=1234.0,
    )
    token, sep, digest = credential.partition('-')
    assert sep == '-'
    assert token and digest
    path = files.file_of(token)
    # the publication slot holds the file of this process
    assert files.file == path
    assert files.owner == OWNER_RESTART
    assert path.exists()
    # the credential leaves the write only after the file hit the disk, and it
    # judges exactly the bytes that were written
    assert pipe.sent == [b'command:resume:' + credential.encode()]
    payload = path.atomic_read_bytes()
    assert digest == files.checksum(token, payload)
    monkeypatch.setenv(RESUME_TOKEN_ENV, credential)
    record = files.read()
    assert isinstance(record, ResumeRecord)
    assert list(record.configs) == ['config-a', 'config-b']
    assert list(record.actions) == ['cleanup']
    assert record.owner == OWNER_RESTART
    assert record.updated_all_at == 1234.0
    assert record.ts > 0
    # the file is read at most once and never survives its read
    assert not path.exists()
    assert files.read() is None


async def test_a_tampered_payload_is_dropped(files, monkeypatch):
    credential = await files.write(['config-a'])
    token = credential.partition('-')[0]
    path = files.file_of(token)
    path.atomic_write(b'{"ts": 0.0}')
    monkeypatch.setenv(RESUME_TOKEN_ENV, credential)
    assert files.read() is None
    # the read is one-shot whatever the verification result
    assert not path.exists()


async def test_a_record_the_writer_never_produced_is_dropped(files, monkeypatch):
    """
    A payload the credential matches but that is not a ``ResumeRecord`` (the
    fields are missing): msgspec raises a ValidationError, the read reports it.
    """
    credential = await files.write(['config-a'])
    token = credential.partition('-')[0]
    path = files.file_of(token)
    payload = b'{}'
    path.atomic_write(payload)
    checksum = files.checksum(token, payload)
    monkeypatch.setenv(RESUME_TOKEN_ENV, f'{token}-{checksum}')
    assert files.read() is None
    assert not path.exists()


@pytest.mark.xfail(
    strict=True,
    reason='read() catches msgspec.ValidationError only, while a payload that is '
    'not JSON at all raises msgspec.DecodeError, although the docstring promises '
    'None for a malformed payload',
)
async def test_a_payload_that_is_not_json_is_dropped(files, monkeypatch):
    """
    A syntactically invalid payload with a matching credential.

    ``read()`` documents ``None`` for a malformed payload; the module only
    catches ``msgspec.ValidationError`` and invalid JSON raises
    ``msgspec.DecodeError`` (its parent class). Kept as a strict xfail so the
    gap stays visible instead of being silently encoded as "the code raises".
    """
    credential = await files.write(['config-a'])
    token = credential.partition('-')[0]
    path = files.file_of(token)
    payload = b'{not json'
    path.atomic_write(payload)
    monkeypatch.setenv(RESUME_TOKEN_ENV, f'{token}-{files.checksum(token, payload)}')
    assert files.read() is None


async def test_withdraw_removes_the_file_and_retracts_the_credential(files, pipe):
    # an idle withdrawal is a no-op: nothing of this process was published
    assert await files.withdraw() is None
    credential = await files.write(['config-a'])
    path = files.file
    removed = await files.withdraw()
    assert removed == path
    assert not path.exists()
    assert files.file is None
    assert files.owner == ''
    # the retraction is announced after the publication and is the last word
    # the supervisor hears about this process
    assert pipe.sent == [
        b'command:resume:' + credential.encode(),
        b'command:resume:',
    ]
    assert await files.withdraw() is None


def test_cleanup_removes_only_the_stale_resume_files(files, folder):
    """
    The age is produced by aging the file itself (``os.utime``) instead of
    monkeypatching ``RESUME_CLEANUP_AGE``: the threshold is read at call time,
    but an old mtime is what the cleanup actually judges.
    """
    folder.makedirs()
    stale = folder.joinpath(f'{RESUME_FILE_PREFIX}stale{RESUME_FILE_SUFFIX}')
    fresh = folder.joinpath(f'{RESUME_FILE_PREFIX}fresh{RESUME_FILE_SUFFIX}')
    foreign = folder.joinpath('notes.txt')
    for path in (stale, fresh, foreign):
        path.atomic_write(b'{}')
    age = time.time() - RESUME_CLEANUP_AGE - 60.0
    os.utime(stale, (age, age))
    files.cleanup()
    assert not stale.exists()
    assert fresh.exists()
    # a foreign file of the folder is never touched
    assert foreign.exists()


def test_cleanup_without_a_folder_does_not_raise(tmp_path):
    """
    The cleanup runs at the process startup: a cleanup problem must not block
    the backend, a missing folder has nothing to remove.
    """
    files = ResumeFiles(folder=PathStr.new(str(tmp_path / 'missing')))
    assert files.iter_files() == []
    files.cleanup()
