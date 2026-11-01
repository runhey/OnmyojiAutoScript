"""
Accept-Language parsing and negotiation.

Ported verbatim from alasio/backend/locale/accept_language.py (no OAS side
project has a locale helper yet). The language of a websocket connection is
picked with this module in WebsocketServer._negotiate_lang: first the
``oas_lang`` cookie, then the ``Accept-Language`` header, then the default.
"""


def parse_accept_language(header):
    """
    Parses an Accept-Language header string into a sorted list of language codes
    based on their quality factor (q-factor), using simple string operations.

    This implementation avoids regular expressions for performance and simplicity.

    Args:
        header (str): The raw string from the Accept-Language header.

    Example:
        "fr-CH, fr;q=0.9, en;q=0.8" -> ['fr-CH', 'fr', 'en']

    Returns:
        list[str]: A list of language codes, sorted in descending order of preference.
    """
    if not header:
        return []

    languages = []
    # 1. Split the header into individual language declarations.
    for lang_chunk in header.split(','):
        # 2. Use `partition` to neatly separate the language code from the quality part.
        # This is more efficient than `split(';', 1)` and returns a 3-tuple.
        # e.g., "fr;q=0.9" -> ('fr', ';', 'q=0.9')
        # e.g., "fr-CH"    -> ('fr-CH', '', '')
        lang_code, sep, q_str = lang_chunk.strip().partition(';')
        lang_code = lang_code.strip()

        # Only process if a language code exists.
        if lang_code:
            quality = 1.0  # Default quality is 1.0 as per RFC 7231.

            # 3. If a separator (';') was found, parse the quality factor.
            if sep:
                # Use `partition` again to separate "q=" from its value.
                # e.g., "q=0.9" -> ('', 'q=', '0.9')
                _, q_sep, q_val = q_str.strip().partition('q=')
                if q_sep:  # This confirms that "q=" was present.
                    try:
                        quality = float(q_val)
                    except ValueError:
                        # Ignore malformed quality factors, the default of 1.0 remains.
                        pass

            languages.append((lang_code, quality))

    # 4. Sort the list of languages by quality in descending order.
    languages.sort(key=lambda x: x[1], reverse=True)

    # 5. Return only the sorted language codes.
    return [lang for lang, q in languages]


def _normalize(locale: str) -> str:
    """Converts a locale string to a canonical form: lowercase with hyphens."""
    locale = locale.lower()
    if '_' in locale:
        locale = locale.replace('_', '-')
    return locale


def negotiate_locale(preferred, available):
    """
    Finds the best match between a list of preferred locales and available locales.

    This function automatically handles both hyphenated ('-') and underscored ('_')
    separators by normalizing them to a canonical form before matching. It also
    handles case-insensitivity, aliases, and language fallbacks (e.g., matching
    'en-US' to 'en').

    Args:
        preferred (list[str] | tuple[str]): A list of locales preferred by the user, ideally sorted by priority.
        available (list[str] | tuple[str]): A list of locales the application supports.

    Returns:
        str: The best-matching locale string from the *original* `available` list,
             or empty string "" if no match is found.
    """
    # This dictionary of aliases helps to resolve common but non-standard
    # or incomplete language codes to their more specific counterparts.
    # Note that this is an in-function table to save memory, as we don't need to call this function frequently.
    # e.g., 'en' -> 'en-US', 'no' -> 'nb-NO' (Norwegian Bokmål)
    aliases = {
        'ar': 'ar-SY',
        'bg': 'bg-BG',
        'bs': 'bs-BA',
        'ca': 'ca-ES',
        'cs': 'cs-CZ',
        'da': 'da-DK',
        'de': 'de-DE',
        'el': 'el-GR',
        'en': 'en-US',
        'es': 'es-ES',
        'et': 'et-EE',
        'fa': 'fa-IR',
        'fi': 'fi-FI',
        'fr': 'fr-FR',
        'gl': 'gl-ES',
        'he': 'he-IL',
        'hu': 'hu-HU',
        'id': 'id-ID',
        'is': 'is-IS',
        'it': 'it-IT',
        'ja': 'ja-JP',
        'km': 'km-KH',
        'ko': 'ko-KR',
        'lt': 'lt-LT',
        'lv': 'lv-LV',
        'mk': 'mk-MK',
        'nl': 'nl-NL',
        'nn': 'nn-NO',
        'no': 'nb-NO',
        'pl': 'pl-PL',
        'pt': 'pt-PT',
        'ro': 'ro-RO',
        'ru': 'ru-RU',
        'sk': 'sk-SK',
        'sl': 'sl-SI',
        'sv': 'sv-SE',
        'th': 'th-TH',
        'tr': 'tr-TR',
        'uk': 'uk-UA',
        'zh': 'zh-CN',
        'zh-hans': 'zh-CN',
        'zh-hans-cn': 'zh-CN',
        'zh-hant': 'zh-TW',
        'zh-hant-tw': 'zh-TW',
    }

    # Create a mapping from a normalized locale to its original cased/separated form.
    # This allows us to return the exact string from the `available` list.
    # e.g., {'en-us': 'en_US', 'zh-hans': 'zh-Hans'}
    dict_norm_available = {_normalize(loc): loc for loc in available}

    for locale in preferred:
        # Normalize the preferred locale for comparison.
        norm_pref = _normalize(locale)

        # 1. Direct match (e.g., 'en-us' matches 'en_US' or 'en-us' in available)
        if norm_pref in dict_norm_available:
            return dict_norm_available[norm_pref]

        # 2. Alias match (e.g., preferred 'no' matches available 'nb_NO')
        # Note: Alias lookup keys are typically simple language codes, not region-specific.
        # We look up the alias using the simple lowercased string, as per Babel's logic.
        alias = aliases.get(norm_pref)
        if alias:
            # Normalize the *result* of the alias lookup for comparison.
            norm_alias = _normalize(alias)
            if norm_alias in dict_norm_available:
                return dict_norm_available[norm_alias]

        # 3. Fallback match (e.g., preferred 'en-gb' matches available 'en')
        primary_lang, _, _ = norm_pref.partition('-')
        if primary_lang != norm_pref and primary_lang in dict_norm_available:
            return dict_norm_available[primary_lang]

    return ''


def negotiate_accept_language(header, available, default=''):
    """
    Parses an Accept-Language header string into one available language.

    Args:
        header (str):  The raw string from the Accept-Language header.
        available (list[str] | tuple[str]): A list of locales the application supports.
            Example: ['zh-CN', 'zh-TW', 'en-US', 'ja-JP']
        default (str): Default language if negotiate failed

    Returns:
        str:
    """
    preferred = parse_accept_language(header)
    lang = negotiate_locale(preferred, available)
    if lang:
        return lang
    else:
        return default
