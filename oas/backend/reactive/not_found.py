class _NotFoundType:
    """Internal type for value not found"""

    def __repr__(self):
        return "<NOT_FOUND>"

    def __bool__(self):
        # default to false, so we can use `if value`
        return False

    def __reduce__(self):
        # pickle-able
        return "_NOT_FOUND"


_NOT_FOUND = _NotFoundType()
