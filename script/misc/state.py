import copy
import functools
import types
from typing import TYPE_CHECKING, Any

import msgspec
from msgspec._core import Factory
from msgspecerror import get_class_annotation_dict

from oas.logger import logger


class _StateBatchContext:
    """Context manager for batch-setting multiple state fields in a single update."""

    def __init__(self, cls):
        self.cls = cls
        self._buffer = {}

    def __enter__(self):
        buffers = self.cls.__batch_buffers__
        buffers.append(self._buffer)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        buffers = self.cls.__batch_buffers__
        if buffers:
            buffers.pop()
        if self._buffer:
            self.cls.update(**self._buffer)


class _StateMeta(type):
    if TYPE_CHECKING:
        __struct_model__: "type[msgspec.Struct]"
        __dict_defaults__: "dict[str, Any]"
        __batch_buffers__: "list[dict[str, Any]]"

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        # gather all fields
        dict_annotations = get_class_annotation_dict(cls)
        struct_fields = []
        for attr, anno in dict_annotations.items():
            try:
                default = getattr(cls, attr)
            except AttributeError:
                raise TypeError(f'State field {cls.__name__}.{attr} must have a default')
            # Wrap non-empty mutable collections with default_factory
            # to avoid msgspec.defstruct rejecting them as unsafe defaults
            # empty mutable collections will be auto converted to factory at msgspec internal
            if isinstance(default, (list, dict, set)) and default:
                default = msgspec.field(default_factory=lambda v=copy.deepcopy(default): v)
            struct_fields.append((attr, anno, default))

        # create struct model
        struct_model: "type[msgspec.Struct]" = msgspec.defstruct(
            f'{cls.__name__}Struct', struct_fields, omit_defaults=True,
        )
        if len(struct_model.__struct_fields__) != len(struct_model.__struct_defaults__):
            raise ValueError(f'All fields in state class {cls.__name__} must have a default value')

        # gather default values
        dict_defaults = {}
        for name, value in zip(struct_model.__struct_fields__, struct_model.__struct_defaults__):
            if value is msgspec.UNSET:
                continue
            if value is msgspec.NODEFAULT:
                raise ValueError(f'State field {cls.__name__}.{name} must have a default value')
            if isinstance(value, Factory):
                # Mutable default wrapped with Factory; call it to get the default
                value = value.factory()
            dict_defaults[name] = value

        # Use super().__setattr__ to bypass the custom __setattr__ hook
        # since struct_model and dict_defaults are internal, not state fields
        super().__setattr__('__struct_model__', struct_model)
        super().__setattr__('__dict_defaults__', dict_defaults)
        # batch buffer stack, lazily populated by batch_set()
        super().__setattr__('__batch_buffers__', [])

    def __call__(cls, *args, **kwargs):
        raise TypeError(
            f"State class '{cls.__name__}' cannot be instantiated. "
            f"Please use class attributes directly (e.g., {cls.__name__}.field_name)."
        )

    def update(cls, **kwargs):
        """
        Update state with kwargs.
        Only attributes that already exist in the state class will be merged.

        Args:
            kwargs: key-value pairs to update
        """
        # may raise ValidationError
        obj = msgspec.convert(kwargs, cls.__struct_model__)
        for name in kwargs:
            if name not in cls.__dict_defaults__:
                continue
            # if validate success, set to class attribute
            # value type may change after validation
            value = getattr(obj, name)
            super().__setattr__(name, value)

    def batch_set(cls):
        """
        Context manager to batch multiple attribute sets into a single update.

        Usage:
            with GameState.batch_set():
                GameState.server = 'jp'
                GameState.lang = 'ja-JP'
            # Single update call here
        """
        return _StateBatchContext(cls)

    def update_from_class(cls, override):
        """
        Merge class attributes from an override class into this state class.
        Only attributes that already exist in the state class will be merged.

        Args:
            override: Any class whose attributes to merge, or an instance of a class to merge
                `override` does not need to be a state class, it can be any class or any instance
        """
        names = dir(override)
        kwargs = {}
        for name in names:
            if name.startswith('__') and name.endswith('__'):
                continue
            # this shouldn't raise Attribute error
            value = getattr(override, name)
            kwargs[name] = value

        cls.update(**kwargs)

    def __setattr__(cls, name, value):
        buffers = cls.__batch_buffers__
        if buffers:
            buffers[-1][name] = value
        else:
            data = {name: value}
            cls.update(**data)

    def is_modified(cls, name):
        """
        Args:
            name (str):

        Returns:
            bool: true if attr is modified
        """
        try:
            default = cls.__dict_defaults__[name]
            value = getattr(cls, name)
        except (KeyError, AttributeError):
            raise ValueError(f'State field {cls.__name__}.{name} does not exist')
        return value != default

    def get_default(cls, name):
        """
        Args:
            name (str):

        Returns:
            Any: default value of attr
        """
        try:
            return cls.__dict_defaults__[name]
        except KeyError:
            raise ValueError(f'State field {cls.__name__}.{name} does not exist')

    def reset_field(cls, name):
        """
        Reset an attr to default value

        Args:
            name (str):
        """
        try:
            default = cls.__dict_defaults__[name]
        except KeyError:
            raise ValueError(f'State field {cls.__name__}.{name} does not exist')
        if isinstance(default, (list, dict, set)):
            default = copy.deepcopy(default)
        super().__setattr__(name, default)

    def reset_all_fields(cls):
        """
        Reset all attrs to default values
        """
        for name, value in cls.__dict_defaults__.items():
            if isinstance(value, (list, dict, set)):
                value = copy.deepcopy(value)
            super().__setattr__(name, value)

    def _iter_all_subclasses(cls):
        """
        Iterate all subclasses

        Yields:
            Type[StateBase]: subclass
        """
        stack = set(cls.__subclasses__())
        while True:
            new_stack = set()
            for subclass in stack:
                yield subclass
                new_stack.update(subclass.__subclasses__())
            if not new_stack:
                break
            stack = new_stack

    def reset_all_subclasses(cls):
        """
        Reset all subclasses' fields to default values
        """
        subclasses = list(cls._iter_all_subclasses())
        for subclass in subclasses:
            subclass.reset_all_fields()

    def match(cls, **kwargs):
        """
        Args:
            **kwargs:

        Returns:
            bool: True if state matches given condition
        """
        matched = True
        for key, value in kwargs.items():
            try:
                if getattr(cls, key) != value:
                    matched = False
                    break
            except AttributeError:
                matched = False
                break
        return matched

    def when(cls, **kwargs):
        """
        Return a decorator that runs the function only if the state class matches the condition

        Examples:
            @GameState.when(server='cn')
            def commission_parse(...):
                # this only runs when server='cn'

            @GameState.when(server='en')
            @GameState.when(server='jp')
            def commission_parse(...):
                # this only runs when server='en' or server='jp'

            @GameState.when()
            def commission_parse(...):
                # fallback method if no conditions matched
                # If no fallback method is defined and state doesn't match the condition above,
                # calling commission_parse() will do nothing and return None

            # the correct method will be called, depending on state
            result = commission_parse(...)

        Note that when using with @classmethod or @staticmethod, when() should at inner
        Examples:
            @classmethod
            @GameStateBase.when(server='cn')
            def class_method(cls):
                return f'class_method_on_{cls.__name__}'

        Note that if no fallback method is defined and current state doesn't match any conditions,
        the last defined method will be called.
        """

        def decorator(func):
            # unique key
            key = (func.__module__, func.__qualname__)

            if key not in _StateDispatcher.REGISTRY:
                dispatcher = _StateDispatcher(func, cls)
                _StateDispatcher.REGISTRY[key] = dispatcher
            else:
                dispatcher = _StateDispatcher.REGISTRY[key]

            # if decorator is chained, extract the function from last case
            if isinstance(func, _StateDispatcher):
                try:
                    func = dispatcher.cases[-1][1]
                except IndexError:
                    # this shouldn't happen
                    pass

            # replace existing entry with same kwargs, or append new one
            # this prevents unbounded growth when when() decorates dynamically defined functions
            for i, (cond, _) in enumerate(dispatcher.cases):
                if cond == kwargs:
                    dispatcher.cases[i] = (kwargs, func)
                    break
            else:
                dispatcher.cases.append((kwargs, func))
            return dispatcher

        return decorator


class GlobalState(metaclass=_StateMeta):
    """
    A global state class
    Note that every field must have typehint and static default value (not default factory).

    Examples:
        class GlobalState(TaskState):
            server: Literal['cn', 'en'] = 'cn'
            lang: Literal['zh-CN', 'en'] = 'zh-CN'

        if not GlobalState.server == 'cn':
            GlobalState.server = 'cn'
    """
    pass


class TaskState(metaclass=_StateMeta):
    """
    A state class that resets on task switch
    Note that every field must have typehint and static default value (not default factory).

    Examples:
        class CampaignState(TaskState):
            is_clear_mode: bool = False
            is_fleet_lock: bool = False

        if not CampaignState.is_clear_mode:
            CampaignState.is_fleet_lock = False
    """
    pass


class _StateDispatcher:
    # key: (module name, qualname), value: callable function
    REGISTRY = {}

    def __init__(self, first_func, state_cls: "_StateMeta"):
        self.state_cls = state_cls
        # [(conditions_dict, target_function)]
        self.cases = []
        functools.update_wrapper(self, first_func)

    def __call__(self, *args, **call_kwargs):
        fallback_func = None
        last_func = None

        for cond, func in self.cases:
            last_func = func
            if not cond:
                fallback_func = func
                continue
            if self.state_cls.match(**cond):
                return func(*args, **call_kwargs)

        if fallback_func is not None:
            return fallback_func(*args, **call_kwargs)

        if last_func is not None:
            logger.warning(
                f'{self.state_cls.__name__}.when() no condition matched for {last_func.__name__!r}, '
                f'using last defined function on {self.state_cls.__name__}'
            )
            return last_func(*args, **call_kwargs)

        return None

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return types.MethodType(self, instance)


class _StatePatchContext:
    """
    Context manager that temporarily patches state fields, the previous values are restored on exit
    """

    def __init__(self, cls, patch):
        """
        Args:
            cls (type): state class, all fields in `patch` must exist in the state class
            patch (dict): field names and the temporary values
        """
        self.cls = cls
        self.patch = patch
        # {name: (is_own_attribute, previous_value)}
        self.snapshot = {}

    def __enter__(self):
        for name in self.patch:
            # field name is validated by GameStateBase.patch()
            value = getattr(self.cls, name)
            if isinstance(value, (list, dict, set)):
                # copy mutable containers, in case they are modified in place
                # by the code being tested
                value = copy.deepcopy(value)
            self.snapshot[name] = (name in self.cls.__dict__, value)
        # atomic, nothing is patched if validation fails
        self.cls.update(**self.patch)
        return self.cls

    def __exit__(self, exc_type, exc_val, exc_tb):
        # restore through update() to bypass any active batch_set() buffer
        restore = {name: value for name, (is_own, value) in self.snapshot.items() if is_own}
        if restore:
            self.cls.update(**restore)
        for name, (is_own, value) in self.snapshot.items():
            if not is_own:
                # the field is inherited, drop the patched attribute
                # so that the value of the parent class takes effect again
                delattr(self.cls, name)


class GameStateBase(GlobalState):
    """
    Examples:
        # Define your GameState
        # All fields should have default value
        class GameState(GameStateBase):
            server: t.Literal['cn', 'en', 'jp', 'tw'] = 'cn'
    """
    server: str = 'cn'
    lang: str = 'zh-CN'

    @classmethod
    def match_server(cls, *server):
        """
        Args:
            *server: server names

        Returns:
            bool: True if any server matches the current state
        """
        for item in server:
            if cls.match(server=item):
                return True
        return False

    @classmethod
    def match_lang(cls, *lang):
        """
        Args:
            *lang: language names

        Returns:
            bool: True if any language matches the current state
        """
        for item in lang:
            if cls.match(lang=item):
                return True
        return False

    @classmethod
    def patch(cls, **kwargs):
        """
        Return a decorator that patches state fields while the decorated function is running,
        the previous values are restored afterwards, even if the function raises

        Examples:
            @GameState.patch(server='en', lang='en-US')
            def test_commission_en():
                # GameState.server == 'en' and GameState.lang == 'en-US' inside the function
                ...
            # GameState.server and GameState.lang are restored here

            # nested patches are restored in reverse order
            @GameState.patch_server('en')
            @GameState.patch_lang('en-US')
            def test_nested():
                ...

        Args:
            kwargs: state fields to patch, e.g. server='en'

        Returns:
            callable: decorator for a sync or async function
        """
        # local import, only needed when a patch decorator is created
        import inspect

        for name in kwargs:
            # update() silently ignores unknown fields, which would make
            # a typo silently patch nothing, so fail fast instead
            if name not in cls.__dict_defaults__:
                raise ValueError(f'State field {cls.__name__}.{name} does not exist')

        def decorator(func):
            if inspect.iscoroutinefunction(func):
                @functools.wraps(func)
                async def wrapper(*args, **call_kwargs):
                    with _StatePatchContext(cls, kwargs):
                        return await func(*args, **call_kwargs)
            else:
                @functools.wraps(func)
                def wrapper(*args, **call_kwargs):
                    with _StatePatchContext(cls, kwargs):
                        return func(*args, **call_kwargs)

            # `functools.wraps` only sets `__wrapped__`, which pytest does not always follow
            # when resolving test arguments, so copy the signature explicitly
            wrapper.__signature__ = inspect.signature(func)
            return wrapper

        return decorator

    @classmethod
    def patch_server(cls, server):
        """
        Return a decorator that patches the server field while the decorated function is running

        Examples:
            @GameState.patch_server('en')
            def test_commission_en():
                # GameState.server == 'en' inside the function
                ...
            # GameState.server is restored here

        Args:
            server (str): server to patch

        Returns:
            callable: decorator for a sync or async function
        """
        return cls.patch(server=server)

    @classmethod
    def patch_lang(cls, lang):
        """
        Return a decorator that patches the lang field while the decorated function is running

        Examples:
            @GameState.patch_lang('en-US')
            def test_commission_en():
                # GameState.lang == 'en-US' inside the function
                ...
            # GameState.lang is restored here

        Args:
            lang (str): language to patch

        Returns:
            callable: decorator for a sync or async function
        """
        return cls.patch(lang=lang)


class _ConfigDispatcher:
    """
    Dispatcher for Config.when() decorated methods.

    When called, checks each condition against the instance's config attribute
    and dispatches to the matching method.
    """

    def __init__(self, first_func):
        self.cases = []
        functools.update_wrapper(self, first_func)

    def __call__(self, *args, **call_kwargs):
        try:
            instance = args[0]
        except IndexError:
            raise TypeError(
                f'{self.__name__} must be called as a bound method, '
                f'method decorated by Config.when() must have `self` as first argument'
            )
        try:
            config = instance.config
        except AttributeError:
            raise AttributeError(f'Method decorated by Config.when() must have `self.config`')
        fallback_func = None
        last_func = None

        for cond, func in self.cases:
            last_func = func
            if not cond:
                fallback_func = func
                continue
            matched = True
            for key, value in cond.items():
                config_value = getattr(config, key)
                if config_value != value:
                    matched = False
                    break
            if matched:
                return func(*args, **call_kwargs)

        if fallback_func is not None:
            return fallback_func(*args, **call_kwargs)

        if last_func is not None:
            logger.warning(
                f'Config.when() no condition matched for {last_func.__name__!r}, '
                f'using last defined function'
            )
            return last_func(*args, **call_kwargs)

        return None

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return types.MethodType(self, instance)


class Config:
    """
    Config class with when() decorator for method dispatch.

    Examples:
        class MyTask:
            config = MyConfig()

            @Config.when(DEVICE_SCREENSHOT_METHOD='adb')
            def screenshot(self):
                ...
    """

    # key: (module name, qualname), value: callable function
    REGISTRY = {}

    @classmethod
    def when(cls, **kwargs):
        """
        Return a decorator that runs the method only if config matches the condition.

        The decorated method must have `self` as first argument,
        and the instance must have a `config` attribute.

        Examples:
            @Config.when(DEVICE_SCREENSHOT_METHOD='adb')
            def screenshot(self):
                # this only runs when self.config.DEVICE_SCREENSHOT_METHOD == 'adb'

            @Config.when(DEVICE_SCREENSHOT_METHOD='adb')
            @Config.when(DEVICE_SCREENSHOT_METHOD='uiautomator2')
            def screenshot(self):
                # this runs when either condition matches

            @Config.when()
            def screenshot(self):
                # fallback method if no conditions matched
        """

        def decorator(func):
            key = (func.__module__, func.__qualname__)

            if key not in cls.REGISTRY:
                dispatcher = _ConfigDispatcher(func)
                cls.REGISTRY[key] = dispatcher
            else:
                dispatcher = cls.REGISTRY[key]

            # if decorator is chained, extract the function from last case
            if isinstance(func, _ConfigDispatcher):
                try:
                    func = dispatcher.cases[-1][1]
                except IndexError:
                    pass

            # replace existing entry with same kwargs, or append new one
            # this prevents unbounded growth when decorating dynamically defined methods
            for i, (cond, _) in enumerate(dispatcher.cases):
                if cond == kwargs:
                    dispatcher.cases[i] = (kwargs, func)
                    break
            else:
                dispatcher.cases.append((kwargs, func))

            return dispatcher

        return decorator
