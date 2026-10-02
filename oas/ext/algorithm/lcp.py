from __future__ import annotations

from typing import overload


@overload
def get_lcp(s1: str, s2: str) -> str: ...


@overload
def get_lcp(s1: bytes, s2: bytes) -> bytes: ...


def get_lcp(s1, s2):
    """
    Get LCP (longest common prefix) of two string

    Args:
        s1 (str | bytes): First string or bytes
        s2 (str | bytes): Second string or bytes

    Returns:
        str | bytes: Longest common prefix, same type as inputs
    """
    i = 0
    # use zip() to iter both at the same time
    # adding index manual is a little faster than enumerate
    for char1, char2 in zip(s1, s2):
        if char1 != char2:
            return s1[:i]
        i += 1
    # compare directly is faster than min()
    str_min = s1 if s1 < s2 else s2
    return str_min


@overload
def get_lcp_length(s1: str, s2: str) -> int: ...


@overload
def get_lcp_length(s1: bytes, s2: bytes) -> int: ...


def get_lcp_length(s1, s2):
    """
    Get LCP length of two strings

    Args:
        s1 (str | bytes): First string or bytes
        s2 (str | bytes): Second string or bytes

    Returns:
        int: Length of the longest common prefix
    """
    i = 0
    for char1, char2 in zip(s1, s2):
        if char1 != char2:
            return i
        i += 1
    return i


@overload
def get_lcs(s1: str, s2: str) -> str: ...


@overload
def get_lcs(s1: bytes, s2: bytes) -> bytes: ...


def get_lcs(s1, s2):
    """
    Get LCS (longest common suffix) of two string

    Args:
        s1 (str | bytes): First string or bytes
        s2 (str | bytes): Second string or bytes

    Returns:
        str | bytes: Longest common suffix, same type as inputs
    """
    # use zip() to iter both from the end at the same time
    # adding index manual is a little faster than enumerate
    i = 0
    for char1, char2 in zip(reversed(s1), reversed(s2)):
        if char1 != char2:
            break
        i += 1
    if i:
        return s1[-i:]
    else:
        # slice end to return empty thingy with the same type
        return s1[len(s1):]


@overload
def get_lcs_length(s1: str, s2: str) -> int: ...


@overload
def get_lcs_length(s1: bytes, s2: bytes) -> int: ...


def get_lcs_length(s1, s2):
    """
    Get LCS length of two strings

    Args:
        s1 (str | bytes): First string or bytes
        s2 (str | bytes): Second string or bytes

    Returns:
        int: Length of the longest common suffix
    """
    i = 0
    for char1, char2 in zip(reversed(s1), reversed(s2)):
        if char1 != char2:
            break
        i += 1
    return i
