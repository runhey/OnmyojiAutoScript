"""Structure tests for the default UI menu."""

from oas.config.models.menu import DEFAULT_MENU


def test_categories_are_non_empty_strings_in_insertion_order():
    assert list(DEFAULT_MENU) == [
        'Script',
        'Soul Zones',
        'Daily Task',
        'Liver Emperor Exclusive',
        'Guild',
        'Weekly Task',
        'Activity Task',
    ]
    assert all(category.strip() for category in DEFAULT_MENU)
    assert all(tasks for tasks in DEFAULT_MENU.values())


def test_task_names_are_non_empty_strings():
    tasks = [task for entries in DEFAULT_MENU.values() for task in entries]

    assert tasks
    assert all(isinstance(task, str) and task.strip() for task in tasks)


def test_task_names_are_unique_across_categories():
    tasks = [task for entries in DEFAULT_MENU.values() for task in entries]

    assert len(tasks) == len(set(tasks))


def test_debug_demo_tasks_are_visible_in_the_script_category():
    assert 'DebugTask' in DEFAULT_MENU['Script']
    assert 'DebugSecondTask' in DEFAULT_MENU['Script']
