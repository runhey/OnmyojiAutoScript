import re


def validate_task_name(name: str) -> bool:
    """
    Validate task name, group name, arg name,
    must match regex ^[A-Z][a-zA-Z0-9]*$
    """
    return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))


def validate_nav_name(name: str) -> bool:
    """
    Validate nav name,
    must match regex ^[a-z][a-z0-9]*$
    """
    return bool(re.match(r'^[a-z][a-z0-9]*$', name))
