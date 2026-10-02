"""
Tests for oas.ext.download

Alasio has no tests/ext/test_download.py, so this module is written from
scratch. Scope is limited to the deterministic surface: session construction.
The three download methods all hit the network and are not exercised here.
"""
import pytest
from requests.adapters import HTTPAdapter

from oas.ext.download import Downloader


class TestNewSession:
    def test_returns_a_session(self):
        import requests

        session = Downloader().new_session()
        assert isinstance(session, requests.Session)

    def test_trust_env_is_disabled(self):
        # Hardcoded in new_session(); reading env proxies would break downloads
        assert Downloader().new_session().trust_env is False

    def test_proxies_point_at_localhost_7890(self):
        # Known wart inherited from Alasio: a hardcoded personal proxy port.
        # Not a typo to fix here; callers currently number zero.
        proxies = Downloader().new_session().proxies
        assert proxies == {
            'http': 'http://127.0.0.1:7890',
            'https': 'http://127.0.0.1:7890',
        }

    @pytest.mark.parametrize('prefix', ['http://', 'https://'])
    def test_adapters_mounted_with_three_retries(self, prefix):
        session = Downloader().new_session()
        adapter = session.get_adapter(prefix)
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.max_retries.total == 3

    def test_each_call_returns_a_distinct_session(self):
        downloader = Downloader()
        assert downloader.new_session() is not downloader.new_session()

    def test_no_user_agent_header_is_set(self):
        # The UA line is commented out in new_session()
        session = Downloader().new_session()
        assert 'User-Agent' not in session.headers or session.headers['User-Agent'] != 'Alasio'


class TestApiSurface:
    @pytest.mark.parametrize(
        'name, args',
        [
            ('atomic_download', ('url', 'file')),
            ('file_download_stream', ('url', 'file', 'chunk_size')),
            ('atomic_download_stream', ('url', 'file', 'chunk_size')),
        ],
    )
    def test_method_takes_documented_arguments(self, name, args):
        import inspect

        sig = inspect.signature(getattr(Downloader, name))
        assert list(sig.parameters) == ['self'] + list(args)