from oas.backend.reactive.base_rpc import RPCMethod
from oas.logger import logger

# Framework classes of the topic hierarchy (known, fixed set): never
# instantiated on their own, they leave TOPIC_NAME to the concrete
# business topics below them. The class-level TOPIC_NAME check in
# __init_subclass__ exempts this list by name; add any new framework
# class here (a missing entry surfaces as a class-definition warning).
_FRAMEWORK_TOPICS = frozenset(('BaseTopic',))


class BaseTopic:
    # Topic name of this topic class: the "t" field of its events and the
    # key clients subscribe with. Every concrete topic class must set it
    # (checked at class definition time, see __init_subclass__), so no
    # runtime name resolution is needed -- callers read TOPIC_NAME
    # directly.
    # The following names are preserved:
    # - "error", the builtin topic to give response to invalid input
    TOPIC_NAME = ''
    # A collection of RPC methods
    # Note that this is auto generated and should be static, don't modify it at runtime
    rpc_methods: "dict[str, RPCMethod]" = {}

    def __init_subclass__(cls, **kwargs):
        """
        This hook is called when a class inherits from BaseTopic.
        It collects all methods decorated with @rpc, which have been
        pre-processed into RPCMethod objects by the decorator.
        """
        super().__init_subclass__(**kwargs)

        # Create a new registry for this specific subclass, inheriting from parent
        # This prevents child classes from modifying the parent's registry.
        cls.rpc_methods = {}

        for base in cls.__mro__:
            # stop at self
            if base is BaseTopic:
                break
            for name, member in base.__dict__.items():
                if not callable(member):
                    continue
                if hasattr(member, '_rpc_method_instance'):
                    # The decorator has already done the heavy lifting. We just collect the result.
                    # MRO iterates from the most derived class to the base, so keep the first
                    # (most derived) definition, allowing child classes to override parent methods
                    if name in cls.rpc_methods:
                        continue
                    cls.rpc_methods[name] = member._rpc_method_instance
                    continue

        # TOPIC_NAME must be set on every concrete topic class (checked at
        # class definition time); framework classes are exempt by name
        # (see _FRAMEWORK_TOPICS above).
        if cls.__name__ not in _FRAMEWORK_TOPICS and not cls.TOPIC_NAME:
            logger.warning(f'{cls.__name__}.TOPIC_NAME is not set')
