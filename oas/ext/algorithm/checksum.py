from hashlib import sha1


def checksum_sha1(data):
    """
    Add sha1 checksum at the end of data stream

    Args:
        data (Iterable[bytes]):

    Yields:
        bytes:
    """
    checksum = sha1()
    for row in data:
        yield row
        checksum.update(row)
    yield checksum.digest()
