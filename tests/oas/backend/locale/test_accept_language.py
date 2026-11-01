"""
Unit tests of the Accept-Language helpers (oas/backend/locale).

The negotiation order of a connection (the ``oas_lang`` cookie, then the
Accept-Language header, then the default) is covered end to end by
tests/oas/backend/ws/test_ws_conn_state.py.
"""

from oas.backend.locale.accept_language import (
    negotiate_accept_language,
    negotiate_locale,
    parse_accept_language,
)

# The GUI languages of the built-in OAS mod (ModEntryInfo.oas())
AVAILABLE = ['zh-CN', 'en-US', 'ja-JP', 'zh-TW', 'es-ES']


def test_parse_sorts_by_quality():
    """The q-factor decides the order, not the position in the header."""
    assert parse_accept_language('fr-CH, fr;q=0.9, en;q=0.8') == ['fr-CH', 'fr', 'en']


def test_parse_treats_a_missing_quality_as_the_highest_one():
    assert parse_accept_language('de, en;q=0.5') == ['de', 'en']


def test_parse_keeps_the_header_order_on_equal_quality():
    assert parse_accept_language('zh-CN, ja-JP') == ['zh-CN', 'ja-JP']


def test_parse_ignores_a_malformed_quality():
    """A broken q value keeps the default 1.0 instead of failing the parse."""
    assert parse_accept_language('de;q=abc, en;q=0.5') == ['de', 'en']


def test_parse_skips_empty_chunks():
    assert parse_accept_language('en, , zh-CN') == ['en', 'zh-CN']


def test_parse_returns_nothing_for_an_empty_header():
    assert parse_accept_language('') == []
    assert parse_accept_language(None) == []


def test_negotiate_matches_exactly():
    assert negotiate_locale(['zh-CN'], AVAILABLE) == 'zh-CN'


def test_negotiate_ignores_case_and_separator():
    """A locale is normalized before matching (case, '_' vs '-')."""
    assert negotiate_locale(['EN-us'], AVAILABLE) == 'en-US'
    assert negotiate_locale(['en_US'], ['en_US']) == 'en_US'


def test_negotiate_uses_the_alias_table():
    """A bare or script-only code resolves to the region-specific language."""
    assert negotiate_locale(['zh'], AVAILABLE) == 'zh-CN'
    assert negotiate_locale(['zh-hans'], AVAILABLE) == 'zh-CN'
    assert negotiate_locale(['zh-hant'], AVAILABLE) == 'zh-TW'
    assert negotiate_locale(['ja'], AVAILABLE) == 'ja-JP'


def test_negotiate_falls_back_to_the_primary_language():
    """A region variant matches a bare primary code in ``available``."""
    assert negotiate_locale(['en-GB'], ['en', 'ja-JP']) == 'en'


def test_negotiate_does_not_fall_back_to_a_region_variant():
    """Only a bare primary code catches variants, a region variant does not."""
    assert negotiate_locale(['en-GB'], AVAILABLE) == ''


def test_negotiate_walks_the_preference_order():
    assert negotiate_locale(['kk-KZ', 'ja-JP'], AVAILABLE) == 'ja-JP'


def test_negotiate_returns_the_spelling_of_available():
    """The result comes from ``available``, never from the preferred list."""
    assert negotiate_locale(['en-us'], ['en_US']) == 'en_US'


def test_negotiate_returns_empty_without_a_match():
    assert negotiate_locale(['kk-KZ'], AVAILABLE) == ''
    assert negotiate_locale([], AVAILABLE) == ''


def test_negotiate_accept_language_picks_the_first_match():
    assert negotiate_accept_language('fr-FR, ja-JP;q=0.9', AVAILABLE) == 'ja-JP'


def test_negotiate_accept_language_uses_the_default():
    assert negotiate_accept_language('kk-KZ', AVAILABLE, 'en-US') == 'en-US'
    assert negotiate_accept_language('', AVAILABLE, 'en-US') == 'en-US'
    assert negotiate_accept_language(None, AVAILABLE, 'en-US') == 'en-US'


def test_negotiate_accept_language_defaults_to_empty():
    assert negotiate_accept_language('kk-KZ', AVAILABLE) == ''
