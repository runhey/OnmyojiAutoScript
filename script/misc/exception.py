class ScriptError(Exception):
    """
    This is likely to be a mistake of developers, but sometimes a random issue.
    Scheduler won't retry on ScriptError.
    """
    pass


class TaskStop(Exception):
    """
    Internal exception that raises on task end and captured by scheduler.
    Task will stop immediately and scheduler will run the next task.
    """
    pass


class GameStuckError(Exception):
    """
    Raises on game stuck (taking screenshots for a while but no game clicking)
    Scheduler will kill game and rerun.
    """
    pass


class GameBugError(Exception):
    """
    Raises when game bugged.
    Scheduler will kill game and rerun.
    """
    pass


class GameTooManyClickError(Exception):
    """
    Raises when clicking the same button too many times,
    which is most likely to be a bot bug, thus continue clicking may get detected as game bot
    Scheduler will kill game and rerun.
    """
    pass


class EmulatorNotRunningError(Exception):
    pass


class GameNotRunningError(Exception):
    pass


class GamePageUnknownError(Exception):
    pass


class RequestHumanTakeover(Exception):
    """
    # Alas is unable to handle such error, probably because wrong settings.
    """
    pass
