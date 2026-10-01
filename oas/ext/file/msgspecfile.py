from msgspec import DecodeError
from msgspec.json import Decoder, decode, encode

from oas.ext.cache.resource import ResourceCache, ResourceCacheTTL, T
from oas.ext.path.atomic import atomic_read_bytes, atomic_write


def read_msgspec(file, default_factory=dict):
    """
    Read json from file using msgspec, return default when having error

    Args:
        file (str):
        default_factory (callable):

    Returns:
        Any:
    """
    try:
        data = atomic_read_bytes(file)
    except FileNotFoundError:
        return default_factory()
    try:
        return decode(data)
    except DecodeError:
        # msgspec.DecodeError: Input data was truncated
        return default_factory()


def write_msgspec(file, obj, skip_same=False):
    """
    Encode obj and write into file using msgspec

    Args:
        file (str):
        obj (Any):
        skip_same (bool):
            True to skip writing if existing content is the same as content to write.
            This would reduce disk write but add disk read

    Returns:
        bool: if write
    """
    data = encode(obj)
    if skip_same:
        try:
            old = atomic_read_bytes(file)
            if data == old:
                return False
        except FileNotFoundError:
            pass

    atomic_write(file, data)
    return True


def deepcopy_msgpack(data):
    """
    Deepcopy a json compatible object, by encoding decoding it.
    This function is 7x faster than vanilla deepcopy.

    ================================================================
    Performance Test Results
    ================================================================
    Function                     Iterations   Average      Slower
    ----------------------------------------------------------------
    rebuild_msgpack              318          972.150us    (fastest)
    rebuild_json                 279          1.060ms      1.09x
    pickle_deepcopy              147          1.952ms      2.01x
    deepcopy                     40           7.832ms      8.06x
    ----------------------------------------------------------------
    """
    return decode(encode(data))


class JsonCache(ResourceCache):
    def load_resource(self, file: str, decoder: Decoder = None) -> T:
        content = atomic_read_bytes(file)
        if decoder is None:
            return decode(content)
        else:
            return decoder.decode(content)


class JsonCacheTTL(ResourceCacheTTL):
    def load_resource(self, file: str, decoder: Decoder = None) -> T:
        content = atomic_read_bytes(file)
        if decoder is None:
            return decode(content)
        else:
            return decoder.decode(content)
