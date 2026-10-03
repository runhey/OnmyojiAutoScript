import inspect

from msgspec import ValidationError, convert

SIG_EMPTY = inspect.Signature.empty


class RPCMethod:
    def __init__(self, func, require_electron=False):
        """
        Args:
            func (callable):
            require_electron (bool): Whether this rpc needs a valid
                electron token (X-Alasio-Token verified against the
                backend token table) before it may execute. Defaults to
                False.
        """
        self.func = func
        self.require_electron = require_electron
        # key: arg name (without "self"), value: arg default,
        # if arg has no default, value is SIG_EMPTY
        self.dict_default = {}
        # key: arg name (without "self"), value: arg annotation,
        # if arg has no default, value is SIG_EMPTY
        self.dict_annotation = {}

        self.build()

    def build(self):
        """
        Build func arg info
        """
        dict_default = self.dict_default
        dict_annotation = self.dict_annotation

        sig = inspect.signature(self.func)
        for name, arg in sig.parameters.items():
            if name == 'self':
                continue
            if arg.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                # *args / **kwargs are not rpc arguments, skip them
                continue
            dict_default[name] = arg.default
            dict_annotation[name] = arg.annotation

    def convert(self, event_value):
        """
        Convert value (RequestEvent.v) to function input

        Returns:
            dict[str, Any]:

        Raises:
            ValidationError:
        """
        kwargs = {}
        dict_annotation = self.dict_annotation
        for name, default in self.dict_default.items():
            # try to get arg from input
            try:
                value = event_value.get(name, default)
            except Exception:
                # event_value is not a dict
                raise ValidationError(f'Input is not a dict')

            # Missing arg and arg has no default
            if value is SIG_EMPTY:
                raise ValidationError(f'Missing arg: "{name}"')

            # try to convert arg
            anno = dict_annotation.get(name, SIG_EMPTY)
            if anno is not SIG_EMPTY:
                try:
                    value = convert(value, anno)
                except ValidationError as e:
                    raise ValidationError(f'Invalid type for arg "{name}": {e}')

            # all good
            kwargs[name] = value

        return kwargs

    def call_sync(self, instance, event_value):
        """
        Args:
            instance (BaseTopic):
            event_value:
        """
        kwargs = self.convert(event_value)
        return self.func(instance, **kwargs)

    async def call_async(self, instance, event_value):
        """
        Args:
            instance (BaseTopic):
            event_value:
        """
        kwargs = self.convert(event_value)
        return await self.func(instance, **kwargs)


def rpc(func=None, *, require_electron=False):
    """
    A decorator that transforms a method into an RPCMethod object and marks it for registration.

    Note that, if an RPC method success, success response will be sent.
    - If an RPC call success, its return value won't be sent.
        You should always send data through topic subscription,
        so every connection can get side effect updates instead of the RPC caller itself.
    - If an RPC call raises error,
        error will be converted to error message and error response will be sent.

    Args:
        func (callable): The method to decorate
        require_electron (bool): Mark the rpc as electron-only: the
            connection must carry a valid electron token (verified before
            the call executes, never inside the method body) or the call
            is rejected with ElectronOnlyError. Defaults to False.

    Examples:
        class ConfigScan(BaseTopic):
            @rpc
            async def config_add(self, name: str, mod: str):
                pass

        class ConnState(BaseTopic):
            @rpc(require_electron=True)
            async def restart(self):
                pass
    """
    if func is None:
        # used as @rpc(require_electron=True)
        return lambda f: rpc(f, require_electron=require_electron)

    # Instead of just setting a flag, we wrap it in an RPCMethod instance immediately.
    # This pre-calculates the parameter processors.
    method = RPCMethod(func, require_electron=require_electron)

    # Store the instance on a special attribute of the original function.
    # The metaclass or __init_subclass__ will find this.
    func._rpc_method_instance = method
    return func
