# This Python file uses the following encoding: utf-8
from functools import wraps
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Config:
    """
    Decorator that calls different function with a same name according to config.

    func_list likes:
    func_list = {
        'func1': [
            {'options': {'ENABLE': True}, 'func': 1},
            {'options': {'ENABLE': False}, 'func': 1}
        ]
    }
    """
    func_list = {}
    """
    这段代码定义了一个名为`Config`的类，其中包含一个名为`when`的装饰器方法。该装饰器用于根据配置的不同，在调用具有相同名称的函数时选择不同的函数。
    在`Config`类中，有一个类变量`func_list`，用于存储函数的配置和对应的函数。`func_list`的结构是一个字典，其中键是函数的名称，值是一个列表，列表中的每个元素是一个字典，包含了选项和对应的函数。每个选项是一个字典，表示配置选项及其值，函数是一个可调用对象。
    `when`装饰器的作用是将装饰的函数添加到`func_list`中。装饰器接受一个或多个关键字参数，这些参数是AzurLaneConfig中的选项。装饰器内部定义了一个`decorate`函数作为装饰器的实际实现。
    在`decorate`函数内部，首先获取被装饰函数的名称和选项，并将它们保存在一个字典中。然后判断该函数名称是否已经存在于`func_list`中，如果不存在，则将该函数及其选项添加到`func_list`中；如果存在，则检查是否有相同选项的记录，如果有，则覆盖原有的函数；如果没有，则添加新的记录。
    接下来，使用`@wraps(func)`装饰器来保留原始函数的元数据。然后定义了一个名为`wrapper`的内部函数作为装饰后的函数。在`wrapper`函数内部，遍历函数名称在`func_list`中的记录，对于每个记录，检查选项是否匹配当前的配置。如果匹配，则调用对应的函数并返回结果；如果没有匹配的选项，则使用最后定义的函数作为默认函数，并打印警告信息。最后，返回`wrapper`函数作为装饰后的函数。
    通过使用`@Config.when()`语法将装饰器应用于函数，可以根据不同的配置选项选择不同的函数执行。
    """

    @classmethod
    def when(cls, **kwargs):
        """
        Args:
            **kwargs: Any option in AzurLaneConfig.

        Examples:
            @Config.when(USE_ONE_CLICK_RETIREMENT=True)
            def retire_ships(self, amount=None, rarity=None):
                pass

            @Config.when(USE_ONE_CLICK_RETIREMENT=False)
            def retire_ships(self, amount=None, rarity=None):
                pass
        """
        from module.logger import logger
        options = kwargs

        def decorate(func):
            name = func.__name__
            data = {'options': options, 'func': func}
            if name not in cls.func_list:
                cls.func_list[name] = [data]
            else:
                override = False
                for record in cls.func_list[name]:
                    if record['options'] == data['options']:
                        record['func'] = data['func']
                        override = True
                if not override:
                    cls.func_list[name].append(data)

            @wraps(func)
            def wrapper(self, *args, **kwargs):
                """
                Args:
                    self: ModuleBase instance.
                    *args:
                    **kwargs:
                """
                for record in cls.func_list[name]:

                    flag = [value is None or self.config.__getattribute__(key) == value
                            for key, value in record['options'].items()]
                    if not all(flag):
                        continue

                    return record['func'](self, *args, **kwargs)

                logger.warning(f'No option fits for {name}, using the last define func.')
                return func(self, *args, **kwargs)

            return wrapper

        return decorate

class cached_property(Generic[T]):
    """
    cached-property from https://github.com/pydanny/cached-property
    Add typing support

    A property that is only computed once per instance and then replaces itself
    with an ordinary attribute. Deleting the attribute resets the property.
    Source: https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76
    """

    def __init__(self, func: Callable[..., T]):
        self.func = func

    def __get__(self, obj, cls) -> T:
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value

def del_cached_property(obj, name):
    """
    Delete a cached property safely.

    Args:
        obj:
        name (str):
    """
    try:
        del obj.__dict__[name]
    except KeyError:
        pass

def has_cached_property(obj, name):
    """
    Check if a property is cached.

    Args:
        obj:
        name (str):
    """
    return name in obj.__dict__



def function_drop(rate=0.5, default=None):
    """
    Drop function calls to simulate random emulator stuck, for testing purpose.

    Args:
        rate (float): 0 to 1. Drop rate.
        default: Default value to return if dropped.

    Examples:
        @function_drop(0.3)
        def click(self, button, record_check=True):
            pass

        30% possibility:
        INFO | Dropped: module.device.device.Device.click(REWARD_GOTO_MAIN, record_check=True)
        70% possibility:
        INFO | Click (1091,  628) @ REWARD_GOTO_MAIN
    """
    from module.logger import logger

    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if random.uniform(0, 1) > rate:
                return func(*args, **kwargs)
            else:
                cls = ''
                arguments = [str(arg) for arg in args]
                if len(arguments):
                    matched = re.search('<(.*?) object at', arguments[0])
                    if matched:
                        cls = matched.group(1) + '.'
                        arguments.pop(0)
                arguments += [f'{k}={v}' for k, v in kwargs.items()]
                arguments = ', '.join(arguments)
                logger.info(f'Dropped: {cls}{func.__name__}({arguments})')
                return default

        return wrapper

    return decorate


def run_once(f):
    """
    Run a function only once, no matter how many times it has been called.

    Examples:
        @run_once
        def my_function(foo, bar):
            return foo + bar

        while 1:
            my_function()

    Examples:
        def my_function(foo, bar):
            return foo + bar

        action = run_once(my_function)
        while 1:
            action()
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)

    wrapper.has_run = False
    return wrapper
