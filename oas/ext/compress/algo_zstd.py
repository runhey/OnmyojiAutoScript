import zstandard as zstd


def zstd_compress(data, source=None, level=22, magicless=True):
    """
    Compress data using zstd with the best compression ratio

    Args:
        data (bytes | memoryview): Data to compress
        source (bytes | memoryview): Old file data as zstd dictionary to compress like `zstd --patch-from`
        level (int): Compression level, 1-22. Defaults to 22.
        magicless (bool): Whether to omit the 4-byte magic header. Defaults to True.

    Returns:
        bytes:
    """
    if source is None:
        dict_data = None
    else:
        dict_data = zstd.ZstdCompressionDict(source)

    params = zstd.ZstdCompressionParameters(
        format=zstd.FORMAT_ZSTD1_MAGICLESS if magicless else zstd.FORMAT_ZSTD1,
        # no checksum because we have our own sha1 checking on old files and new files
        write_checksum=False,
        # write content size so decompressor can pre-allocate memory
        write_content_size=True,
        # no dict_id because it's meaningless in `zstd --patch-from`, which dict_id is always 0
        write_dict_id=False,
    )
    compressor = zstd.ZstdCompressor(
        level=level,
        dict_data=dict_data,
        compression_params=params,
    )
    out = compressor.compress(data)
    return out


def zstd_decompress(data, source=None):
    """
    Args:
        data (bytes | memoryview): Compressed data, accepts any bytes-like
        source (bytes | memoryview): Old file data as zstd dictionary to
            decompress like `zstd -d --patch-from`

    Returns:
        bytes:
    """
    if source is None:
        dict_data = None
    else:
        dict_data = zstd.ZstdCompressionDict(source)

    # Auto-detect format: if data starts with zstd magic header, use default format,
    # otherwise treat as magicless (FORMAT_ZSTD1_MAGICLESS).
    if data[:len(zstd.FRAME_HEADER)] == zstd.FRAME_HEADER:
        fmt = zstd.FORMAT_ZSTD1
    else:
        fmt = zstd.FORMAT_ZSTD1_MAGICLESS

    decompressor = zstd.ZstdDecompressor(
        dict_data=dict_data,
        format=fmt,
    )
    out = decompressor.decompress(data)
    return out
