import tomllib


def toml_loads(data):
    """
    Parse a TOML document.

    Args:
        data (bytes | str): Content of the document, bytes are decoded as
            UTF-8 as the TOML specification requires

    Returns:
        dict: Parsed document

    Raises:
        ValueError: If the content is not a TOML document, TOMLDecodeError is
            a ValueError
    """
    if isinstance(data, (bytes, bytearray)):
        data = data.decode('utf-8')
    return tomllib.loads(data)
