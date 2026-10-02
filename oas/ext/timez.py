import datetime
from typing import Union


def get_local_tz() -> datetime.tzinfo:
    """
    Isolates the call to datetime.now() so it can be easily patched during tests.
    Returns the current system's local timezone info object.
    """
    return datetime.datetime.now().astimezone().tzinfo


def _parse(text):
    """
    Parse an ISO 8601 string on Python 3.14.

    ``datetime.fromisoformat`` has accepted the upper-case 'Z' suffix since
    3.11, so only the lower-case 'z' still needs translating. Kept in one
    place because to_local_naive and to_local_aware both need it.

    Args:
        text (str): An ISO 8601 formatted string. e.g., '2023-10-27T15:30:00Z'

    Returns:
        datetime.datetime:

    Raises:
        ValueError:
        TypeError:
    """
    if isinstance(text, str) and text.endswith('z'):
        text = text[:-1] + '+00:00'
    return datetime.datetime.fromisoformat(text)


def fromisoformat(text) -> datetime.datetime:
    """
    Parse an ISO 8601 string, accepting the lower-case 'z' UTC suffix that
    ``datetime.fromisoformat`` still rejects on Python 3.14.

    Args:
        text (str): An ISO 8601 formatted string. e.g., '2023-10-27T15:30:00Z'

    Returns:
        datetime.datetime:

    Raises:
        ValueError:
        TypeError:
    """
    return _parse(text)


def to_local_naive(time_input: "Union[str, datetime.datetime]") -> datetime.datetime:
    """
    Converts a time input (string or datetime object) to a naive datetime
    object representing the local time.

    Logic:
    - If the input is timezone-aware, it's converted to the local timezone,
      and then the timezone info is removed.
    - If the input is timezone-naive, it's assumed to be in local time
      already and is returned as is.

    Args:
        time_input (Union[str, datetime.datetime]):
            - An ISO 8601 formatted string (e.g., '2023-10-27T15:30:00+08:00').
            - Or a datetime.datetime object (either aware or naive).

    Returns:
        datetime.datetime: A naive datetime object (tzinfo=None) in local time.

    Raises:
        TypeError: If the input is not a string or datetime object.
        ValueError: If the string is not a valid ISO 8601 format.
    """
    # 1. Unify the input into a datetime object
    if isinstance(time_input, str):
        dt_obj = _parse(time_input)
    elif isinstance(time_input, datetime.datetime):
        dt_obj = time_input
    else:
        raise TypeError('Input must be a str or datetime.datetime object')

    # 2. Process based on whether the datetime object is naive or aware
    if dt_obj.tzinfo:
        # Input is an aware object -> convert it to the system's local timezone.
        # Routed through get_local_tz() rather than astimezone(None) so tests
        # can pin the local timezone via monkeypatch.
        local_dt = dt_obj.astimezone(get_local_tz())
        # Remove timezone info to make it naive
        return local_dt.replace(tzinfo=None)
    else:
        # Input is a naive object -> assume it's already in local time and return it
        return dt_obj


def to_local_aware(time_input: "Union[str, datetime.datetime]") -> datetime.datetime:
    """
    Converts a time input (string or datetime object) to an aware datetime
    object representing the local time with local timezone information.

    Logic:
    - If the input is timezone-aware, it's converted to the local timezone.
    - If the input is timezone-naive, it's assumed to be local time, and
      local timezone info is attached to it.

    Args:
        time_input (Union[str, datetime.datetime]):
            - An ISO 8601 formatted string (e.g., '2023-10-27T15:30:00+08:00').
            - Or a datetime.datetime object (either aware or naive).

    Returns:
        datetime.datetime: An aware datetime object with local timezone info.

    Raises:
        TypeError: If the input is not a string or datetime object.
        ValueError: If the string is not a valid ISO 8601 format.
    """
    # 1. Unify the input into a datetime object
    if isinstance(time_input, str):
        dt_obj = _parse(time_input)
    elif isinstance(time_input, datetime.datetime):
        dt_obj = time_input
    else:
        raise TypeError('Input must be a str or datetime.datetime object')

    # Get the local timezone object
    local_tz = get_local_tz()

    # 2. Process based on whether the datetime object is naive or aware
    if dt_obj.tzinfo:
        # Input is an aware object -> convert it to the local timezone
        return dt_obj.astimezone(local_tz)
    else:
        # Input is a naive object -> assume it's local time and attach timezone info
        return dt_obj.replace(tzinfo=local_tz)