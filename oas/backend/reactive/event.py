from typing import Any, Literal, Tuple, Union

from msgspec import Struct, field


class RequestEvent(Struct, omit_defaults=True):
    # Topic, topic name.
    t: str
    # Operation.
    # operation can be omitted, if so, operation is considered to be "sub"
    # if operation is "sub", operation should be omitted
    # if operation is "auth", the message carries a one-time renewal code
    # in "v" to renew the connection's electron token
    o: Literal['sub', 'unsub', 'rpc', 'auth'] = 'sub'
    # Function, RPC function Name.
    # if operation is "sub" or "unsub", "f" should be omitted
    f: str = ''
    # Value, RPC function argument value.
    # if operation is "sub" or "unsub", "v" should be omitted
    # value can be omitted, if so, value is consider to be empty dict {}
    v: Any = field(default_factory=dict)
    # ID, RPC event ID, a random unique ID to track RPC calls.
    # if operation is "sub" or "unsub", "i" should be omitted
    # A ResponseEvent with the same ID will be sent when the RPC event is finished
    i: str = ''


class ResponseEvent(Struct, omit_defaults=True):
    # Topic.
    t: str
    # Operation.
    # operation may be omitted, if so, operation is "add"
    o: Literal['full', 'add', 'set', 'del'] = 'add'
    # Keys.
    # keys may be omitted, if so, keys is (), meaning doing operation at data root
    k: Tuple[Union[str, int], ...] = ()
    # Value.
    # value may be omitted, if so, value is None
    # if operation is "del", value will be omitted
    v: Any = None
    # ID, RPC event ID, a random unique ID to track RPC calls.
    # If present, this event is a response to an RPC call.
    # RPC event ID only comes with topic and value.
    # - If event success, value is omitted.
    # - If event failed, value is a string of error message.
    # An RPC response omitting "v" means success, having "v" means error
    i: str = ''


class AccessDenied(Exception):
    """
    Error raised when a RequestEvent is not allowed (e.g. unknown topic,
    restricted topic or restricted rpc without a valid electron token).

    The message keeps debuggable text: the rejection reason plus the
    topic / rpc name (e.g. 'Topic requires electron: Preview',
    'RPC require_electron: restart'). It must never contain tokens,
    secrets, paths or internal state. The error message is sent
    to the frontend through send_error when the client subscribed the
    error topic.
    """
    pass


class ElectronOnlyError(AccessDenied):
    """
    AccessDenied for electron-restricted operations: the connection does
    not carry a valid electron token (or it was evicted by rotation).
    The frontend recognizes this error by name to trigger a renewal.
    """
    pass


class RpcValueError(Exception):
    """
    Internal error that raises when RPC input value is incorrect.
    This error won't be exposed to frontend.
    """
    pass
