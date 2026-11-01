"""
Password strength rule of the web ui password (``config/deploy.json``
-> ``backend.password``).

The rule is enforced at runtime, deliberately not as a field constraint:
a failing constraint would fall back to the field default, so a
constraint would silently replace the password the user set and the user
could no longer tell what is configured. Instead the configured password
is kept as is, a weak one is reported with a warning at startup and
treated as unset by the admission gate (DeploymentGateMiddleware rule
A): remote access is refused, only the local app client still passes.

The message of the rule lives here too: the startup warning uses it,
and it is the reference text the frontend translation mirrors. The two
are maintained independently and kept in sync by hand (the manual
contract noted on both sides): reword this message first, then follow
up on the frontend side (Alasio keeps the mirror in
``frontend/src/i18n/Auth.json`` under ``t.Auth.ErrDeployPasswordTooWeak``;
the OAS frontend is the Flutter app).
"""

# Message of a password that fails the rule: logged at startup, and the
# reference text of the frontend translation (Alasio:
# t.Auth.ErrDeployPasswordTooWeak in frontend/src/i18n/Auth.json). It is
# the single description of the rule in the backend, keep it in sync
# with the check below whenever the rule changes, and with the frontend
# translation (manual contract).
WEAK_PASSWORD_MESSAGE = (
    'Password too weak: at least 8 characters are required, '
    'please set a new password in config/deploy.json'
)


def is_weak_password(pwd):
    """
    Check whether a password fails the strength rule.

    The rule and WEAK_PASSWORD_MESSAGE are the single policy point of
    the password strength: stronger requirements such as "at least one
    digit and one letter" are added here, and the message above is
    reworded in the same edit (the frontend translation mirrors it).

    Args:
        pwd (str): The password to check, '' when none is configured

    Returns:
        bool: weak_password, True when the password is too weak. An
            empty password is weak too: the caller distinguishes "no
            password" from "weak password" by checking the raw value,
            they lead to different guidance on the login page.
    """
    # length rule for now: at least 8 characters
    weak_password = len(pwd) < 8
    return weak_password
