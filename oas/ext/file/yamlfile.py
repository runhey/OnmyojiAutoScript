import yaml

from oas.ext.path.atomic import atomic_read_bytes, atomic_write

# pyyaml wraps plain scalars at this column, the pyyaml default is 80.
# 120 keeps a long value such as a path or a sentence on the same line as its key
LINE_WIDTH = 120


# https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data/15423007
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)


def yaml_loads(data):
    """
    Args:
        data (bytes):

    Returns:
        Any:
    """
    # Use the C extension if available
    loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
    return yaml.load(data, loader)


def yaml_dumps(obj):
    """
    Encode obj into yaml bytes

    A multiline string is emitted as a literal block scalar, a plain scalar is
    wrapped at LINE_WIDTH (120) instead of the pyyaml default 80.

    Args:
        obj (Any): Object to encode, any object but a list is wrapped into a single document

    Returns:
        bytes:
    """
    # Use the C extension if available
    dumper = getattr(yaml, 'CSafeDumper', yaml.SafeDumper)
    if not isinstance(obj, list):
        obj = [obj]
    return yaml.dump_all(
        obj,
        Dumper=dumper,
        default_flow_style=False,
        encoding='utf-8',
        allow_unicode=True,
        sort_keys=False,
        width=LINE_WIDTH,
    )


def read_yaml(file, default_factory=dict):
    """
    Read yaml from file, return default when having error

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
        return yaml_loads(data)
    except yaml.YAMLError:
        return default_factory()


def write_yaml(file, obj, skip_same=False, formatter=None):
    """
    Encode obj to yaml and write into file

    Args:
        file (str):
        obj (Any):
        skip_same (bool):
            True to skip writing if existing content is the same as content to write.
            This would reduce disk write but add disk read
        formatter (callable): Additional function to format yaml data
            function should receive bytes and return bytes

    Returns:
        bool: if write
    """
    data = yaml_dumps(obj)
    if formatter is not None:
        data = formatter(data)
    if skip_same:
        try:
            old = atomic_read_bytes(file)
            if data == old:
                return False
        except FileNotFoundError:
            pass

    atomic_write(file, data)
    return True


def format_yaml(file, formatter):
    """
    Args:
        file (str): Absolute filepath to yaml file
        formatter (callable): A function that receives bytes and return bytes

    Returns:
        bool: If formatted
    """
    try:
        data = atomic_read_bytes(file)
    except FileNotFoundError:
        # no need to format
        return False
    try:
        yaml_loads(data)
    except yaml.YAMLError:
        # format valid yaml only
        return False
    new = formatter(data)
    if new == data:
        # same content, no need to write
        return False
    atomic_write(file, new)
    return True
