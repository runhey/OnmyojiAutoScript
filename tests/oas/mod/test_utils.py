"""Tests for Mod name validation helpers."""

import pytest

from oas.mod.utils import validate_nav_name, validate_task_name


@pytest.mark.parametrize(
    "name, valid",
    [
        ("FindJade", True),
        ("A", True),
        ("Abc123", True),
        ("findJade", False),
        ("1Abc", False),
        ("", False),
        ("Abc-Def", False),
    ],
)
def test_validate_task_name(name, valid):
    assert validate_task_name(name) is valid


@pytest.mark.parametrize(
    "name, valid",
    [
        ("nav", True),
        ("n1", True),
        ("Nav", False),
        ("1nav", False),
        ("", False),
        ("nav-name", False),
    ],
)
def test_validate_nav_name(name, valid):
    assert validate_nav_name(name) is valid
