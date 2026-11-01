"""
Packed release history decoding.

Ported verbatim from alasio/deploy/history/decode_history.py (the OAS deploy
layer had no history reader): the ModHistory topic decodes
``<mod root>/.pack/history.pack`` with this.
"""

from typing import List

import msgspec


class HistoryObj(msgspec.Struct, array_like=True):
    """
    History of a commit or a tag, used to build release history.

    Encoded as a msgpack array to avoid repeating field names, the
    field order is version, author, time, title, detail.

    Attributes:
        version (str): Version of this history item.
            The tag name for a tag, the commit sha1 for a commit.
        author (str): Author of this history item.
            The tagger name for a tag, the author name for a commit.
        time (int): Time of this history item, unix timestamp in seconds.
            The tag time for a tag, the author time for a commit.
        title (str): Title of this history item.
            The first line of the commit message, empty for a tag.
        detail (str): Detail of this history item.
            The rest of the commit message, empty for a tag.
    """

    version: str
    author: str
    time: int
    title: str
    detail: str


def decode_history(data):
    """
    Decode msgpack encoded history data to a list of HistoryObj.

    Args:
        data (bytes): msgpack encoded history data

    Returns:
        list[HistoryObj]: Decoded history objects

    Raises:
        msgspec.DecodeError: If the data is not valid history data
    """
    return msgspec.msgpack.decode(data, type=List[HistoryObj])
