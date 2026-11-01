"""Tests for the password strength rule of the web ui password."""

import pytest

from oas.backend.auth.password import WEAK_PASSWORD_MESSAGE, is_weak_password


@pytest.mark.parametrize('pwd', ['', 'a', '1234567'])
def test_a_password_shorter_than_eight_characters_is_weak(pwd):
    assert is_weak_password(pwd) is True


@pytest.mark.parametrize('pwd', ['12345678', 'a-long-enough-password'])
def test_a_password_of_at_least_eight_characters_is_not_weak(pwd):
    assert is_weak_password(pwd) is False


def test_an_empty_password_is_weak_too():
    # the caller distinguishes "no password" from "too weak" by the raw value:
    # they lead to different guidance on the login page
    assert is_weak_password('') is True


def test_the_message_states_the_rule_and_where_to_fix_it():
    assert 'at least 8 characters' in WEAK_PASSWORD_MESSAGE
    assert 'deploy.json' in WEAK_PASSWORD_MESSAGE
