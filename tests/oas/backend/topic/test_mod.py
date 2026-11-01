"""
Unit tests of the ModList and ModHistory topics.

Both read the mod layer instead of the connection, so they are covered here;
their registration over the real /api/ws endpoint is pinned by
tests/oas/backend/ws/test_ws_mod_log.py.
"""

from pathlib import Path

import msgspec
import pytest

from oas.backend.topic.mod import (
    ModHistory,
    ModHistorySource,
    ModList,
    ModListSource,
    ModOption,
)
from oas.deploy.history.decode_history import HistoryObj, decode_history
from oas.mod.loader import MOD_LOADER, ModLoader

pytestmark = pytest.mark.anyio

CONN_ID = 'test-conn'
MOD_NAME = 'oas'


@pytest.fixture(autouse=True)
def clear_sources():
    """
    Drop the source singletons around each test.

    ModListSource and ModHistorySource are singletons with a cache TTL, so a
    leftover instance from another test would answer reinit() from its cache
    and hide the disk read.
    """
    ModListSource.singleton_clear()
    ModHistorySource.singleton_clear()
    yield
    ModListSource.singleton_clear()
    ModHistorySource.singleton_clear()


@pytest.fixture(autouse=True)
def clear_topics():
    yield
    ModList.singleton_remove(CONN_ID)
    ModHistory.singleton_remove(CONN_ID)


def history_pack(root: Path, items: 'list[HistoryObj]') -> Path:
    """Write a packed release history into a mod root and return the file."""
    parent = root.joinpath('.pack')
    parent.mkdir(parents=True, exist_ok=True)
    file = parent.joinpath('history.pack')
    file.write_bytes(msgspec.msgpack.encode(items))
    return file


def test_decode_history_round_trips():
    items = [
        HistoryObj(
            version='v1.2.3',
            author='oas',
            time=1700000000,
            title='A release',
            detail='The body',
        )
    ]
    assert decode_history(msgspec.msgpack.encode(items)) == items


def test_decode_history_rejects_foreign_data():
    with pytest.raises(msgspec.DecodeError):
        decode_history(b'not msgpack history')


async def test_mod_list_source_lists_the_declared_mods():
    """
    The list comes from MOD_LOADER.dict_mod, which is the declared entry table
    of the OAS mod layer (a single built-in mod, no Alasio _index folders).
    """
    source = ModListSource()
    await source.reinit()
    assert source.data == [ModOption(value=MOD_NAME, label=MOD_NAME)]
    assert [name for name in MOD_LOADER.dict_mod] == [MOD_NAME]


async def test_mod_list_topic_resolves_the_source():
    source = await ModList(CONN_ID, None).get_source()
    assert isinstance(source, ModListSource)


async def test_mod_history_source_reports_a_failure_per_mod():
    """
    A mod without a packed history is reported, not raised: the topic pushes
    "one entry per mod, empty data plus the error" so the frontend can show
    the reason instead of losing the whole topic.
    """
    source = ModHistorySource()
    await source.reinit()
    assert set(source.data) == {MOD_NAME}
    entry = source.data[MOD_NAME]
    assert entry['data'] == []
    assert 'history.pack' in entry['error']


async def test_mod_history_source_decodes_a_packed_history(tmp_path, monkeypatch):
    """
    The successful branch: a mod root with a real .pack/history.pack is
    decoded to plain dicts (HistoryObj is array_like, the topic must not
    encode it as a list).
    """
    pack = history_pack(
        tmp_path,
        [
            HistoryObj(
                version='v1.0.0', author='oas', time=1, title='First', detail=''
            ),
            HistoryObj(
                version='v1.1.0', author='oas', time=2, title='Second', detail='body'
            ),
        ],
    )

    class FakeMod:
        root = None

    fake = FakeMod()
    fake.root = tmp_path
    monkeypatch.setattr(ModLoader, 'dict_mod', property(lambda self: {MOD_NAME: fake}))

    source = ModHistorySource()
    await source.reinit()
    assert pack.exists()
    assert source.data[MOD_NAME]['data'] == [
        {
            'version': 'v1.0.0',
            'author': 'oas',
            'time': 1,
            'title': 'First',
            'detail': '',
        },
        {
            'version': 'v1.1.0',
            'author': 'oas',
            'time': 2,
            'title': 'Second',
            'detail': 'body',
        },
    ]


async def test_mod_history_topic_resolves_the_source():
    source = await ModHistory(CONN_ID, None).get_source()
    assert isinstance(source, ModHistorySource)
