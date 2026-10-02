import pytest
import zstandard as zstd

from oas.ext.compress.algo_zstd import zstd_compress, zstd_decompress


class TestZstdCompress:
    """Tests for zstd_compress function."""

    def test_magicless_output(self):
        """Default magicless=True should omit the zstd magic header."""
        data = b"Hello Alasio!" * 100
        compressed = zstd_compress(data)
        assert compressed[:4] != zstd.FRAME_HEADER

    def test_magicless_false(self):
        """magicless=False should produce a standard zstd frame with magic header."""
        data = b"Hello Alasio!" * 100
        compressed = zstd_compress(data, magicless=False)
        assert compressed[:4] == zstd.FRAME_HEADER

    @pytest.mark.parametrize("data", [
        pytest.param(b"Hello Alasio Framework! " * 100, id="repeated-ascii"),
        pytest.param(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 50, id="all-byte-values"),
        pytest.param(b"A" * 10000, id="highly-compressible"),
        pytest.param("Hello, 世界! ".encode("utf-8") * 50, id="unicode-utf8"),
        pytest.param(b"\xff" * 1000, id="repeated-high-byte"),
    ])
    def test_compress_decompress_roundtrip(self, data):
        """Compress then decompress should return original data."""
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data
        assert len(compressed) < len(data), (
            f"Compressed size {len(compressed)} should be less than "
            f"original size {len(data)}"
        )

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"a", id="single-byte"),
        pytest.param(b"ab", id="two-bytes"),
        pytest.param(b"Hello", id="short-string"),
        pytest.param(b"a" * 10, id="short-repeated"),
    ])
    def test_small_data_roundtrip(self, data):
        """Small data should survive roundtrip even if not compressed."""
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    def test_large_data_roundtrip(self):
        """Large data should roundtrip correctly."""
        data = b"Hello Alasio! " * 100000
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data
        assert len(compressed) < len(data)

    def test_random_binary_data(self):
        """Random/incompressible binary data should still roundtrip."""
        data = bytes(range(256)) * 100
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    def test_huge_single_block(self):
        """Single large block of data should roundtrip."""
        data = b"X" * 1000000
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    @pytest.mark.parametrize("level", [1, 3, 10, 22])
    def test_with_explicit_level(self, level):
        """Should be usable with different compression levels."""
        data = b"A" * 10000
        from zstandard import ZstdCompressionParameters, ZstdCompressor

        params = ZstdCompressionParameters(
            format=zstd.FORMAT_ZSTD1_MAGICLESS,
            write_checksum=False,
            write_content_size=True,
            write_dict_id=False,
        )
        compressor = ZstdCompressor(
            level=level,
            compression_params=params,
        )
        compressed = compressor.compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data


class TestZstdDecompress:
    """Tests for zstd_decompress function."""

    def test_decompress_magicless_frame(self):
        """Should decompress a magicless zstd frame correctly."""
        data = b"Hello Alasio!" * 100
        compressed = zstd_compress(data)
        assert compressed[:4] != zstd.FRAME_HEADER
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    def test_decompress_normal_frame(self):
        """Should also decompress a standard zstd frame (backward compat)."""
        data = b"Hello Alasio!" * 100
        compressor = zstd.ZstdCompressor(level=22)
        compressed = compressor.compress(data)
        assert compressed[:4] == zstd.FRAME_HEADER
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    def test_decompress_empty(self):
        """Should decompress empty data correctly."""
        compressed = zstd_compress(b"")
        decompressed = zstd_decompress(compressed)
        assert decompressed == b""

    def test_decompress_large(self):
        """Should decompress large data correctly."""
        data = b"Hello Alasio! " * 100000
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data
        assert len(decompressed) == len(data)

    def test_decompress_binary(self):
        """Should decompress binary data correctly."""
        data = bytes(range(256)) * 100
        compressed = zstd_compress(data)
        decompressed = zstd_decompress(compressed)
        assert decompressed == data

    def test_decompress_corrupted_data(self):
        """Should raise ZstdError for corrupted data."""
        with pytest.raises(zstd.ZstdError):
            zstd_decompress(b"this is not zstd compressed data")

    def test_decompress_truncated_data(self):
        """Should raise ZstdError for truncated data."""
        data = b"Hello Alasio!" * 100
        compressed = zstd_compress(data)
        truncated = compressed[:len(compressed) // 2]
        with pytest.raises(zstd.ZstdError):
            zstd_decompress(truncated)


class TestZstdWithDict:
    """Tests for zstd_compress/zstd_decompress with dictionary (patch-from mode)."""

    DICT_DATA = b"This is the original file content that serves as a zstd dictionary." * 50

    @pytest.mark.parametrize("new_data", [
        pytest.param(
            b"This is the modified file content with some changes applied to it." * 50,
            id="similar-to-dict",
        ),
        pytest.param(
            b"This is the original file content that serves as a zstd dictionary." * 50,
            id="identical-to-dict",
        ),
        pytest.param(b"Completely different content that shares nothing with the dict." * 50,
                     id="different-from-dict"),
        pytest.param(b"" * 100, id="empty"),
        pytest.param(b"A" * 1000, id="short-compressible"),
    ])
    def test_dict_roundtrip(self, new_data):
        """Compress with dict, decompress with same dict should return original."""
        compressed = zstd_compress(new_data, source=self.DICT_DATA)
        decompressed = zstd_decompress(compressed, source=self.DICT_DATA)
        assert decompressed == new_data

    def test_dict_smaller_than_no_dict(self):
        """Compression with a matching dict should produce smaller output."""
        new_data = b"This is the modified file content with some changes applied to it." * 50

        compressed_with_dict = zstd_compress(new_data, source=self.DICT_DATA)
        compressed_without_dict = zstd_compress(new_data)

        assert len(compressed_with_dict) <= len(compressed_without_dict)

    def test_dict_wrong_dict_produces_wrong_data(self):
        """Decompressing with wrong dict should produce wrong data (not raise)."""
        data = b"This is some new content that builds upon the original." * 50
        wrong_dict = b"This is a completely different dictionary that does not match." * 50

        compressed = zstd_compress(data, source=self.DICT_DATA)
        try:
            decompressed = zstd_decompress(compressed, source=wrong_dict)
            assert decompressed != data, (
                "Wrong dict should produce different data, not original"
            )
        except zstd.ZstdError:
            # Some dict mismatches may also raise ZstdError; that's acceptable
            pass


class TestZstdRoundtrip:
    """Integration roundtrip tests for compress then decompress."""

    @pytest.mark.parametrize("data, source", [
        pytest.param(b"Short data", None, id="no-dict-short"),
        pytest.param(
            b"A" * 100000,
            None,
            id="no-dict-large",
        ),
        pytest.param(
            b"Modified: " + b"Original content that was used for the patch." * 50,
            b"Original content that was used for the patch." * 50,
            id="with-dict",
        ),
        pytest.param(
            b"This is an updated file with new features and bug fixes!" * 50,
            b"This is the original file before any modifications were made." * 50,
            id="with-dict-different",
        ),
    ])
    def test_roundtrip(self, data, source):
        """Roundtrip should always return original data."""
        compressed = zstd_compress(data, source=source)
        decompressed = zstd_decompress(compressed, source=source)
        assert decompressed == data

    def test_multiple_operations(self):
        """Multiple compression/decompression operations should not interfere."""
        datasets = [
            (b"First dataset with repeated content. " * 50, None),
            (b"Second dataset using dictionary reference. " * 50,
             b"Second dataset using dictionary reference. " * 25),
            (b"Third dataset, completely different. " * 50, None),
        ]
        for data, source in datasets:
            compressed = zstd_compress(data, source=source)
            decompressed = zstd_decompress(compressed, source=source)
            assert decompressed == data

    def test_compress_decompress_streaming(self):
        """Streaming-style decompression should also work."""
        data = b"Hello Alasio Streaming Test! " * 5000
        compressed = zstd_compress(data)

        decompressor = zstd.ZstdDecompressor(format=zstd.FORMAT_ZSTD1_MAGICLESS)
        import io
        buf = io.BytesIO(compressed)
        reader = decompressor.stream_reader(buf)

        chunks = []
        while True:
            chunk = reader.read(4096)
            if not chunk:
                break
            chunks.append(chunk)
        result = b"".join(chunks)
        assert result == data


class TestZstdMemoryview:
    """Tests for memoryview input support in compress and decompress."""

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"Hello Alasio!", id="short"),
        pytest.param(b"Hello Alasio! " * 100, id="medium"),
        pytest.param(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 50, id="all-byte-values"),
        pytest.param(b"A" * 100000, id="highly-compressible"),
    ])
    def test_compress_memoryview(self, data):
        """Compress should accept memoryview input."""
        compressed = zstd_compress(memoryview(data))
        assert zstd_decompress(compressed) == data

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"Hello Alasio!", id="short"),
        pytest.param(b"Hello Alasio! " * 100, id="medium"),
    ])
    def test_decompress_memoryview(self, data):
        """Decompress should accept memoryview input."""
        compressed = zstd_compress(data)
        assert zstd_decompress(memoryview(compressed)) == data

    def test_decompress_memoryview_normal_frame(self):
        """Decompress memoryview of a standard zstd frame with magic header."""
        data = b"Hello Alasio!" * 100
        compressed = zstd_compress(data, magicless=False)
        assert compressed[:4] == zstd.FRAME_HEADER
        assert zstd_decompress(memoryview(compressed)) == data

    def test_memoryview_source(self):
        """source as memoryview should work as zstd dictionary (patch-from)."""
        source = b"Original content that was used for the patch. " * 50
        new_data = b"Modified content that builds upon the original. " * 50
        compressed = zstd_compress(memoryview(new_data), source=memoryview(source))
        assert zstd_decompress(memoryview(compressed), source=memoryview(source)) == new_data

    @pytest.mark.parametrize("level", [1, 3, 22])
    def test_compress_memoryview_with_level(self, level):
        """Compress memoryview with explicit level should roundtrip correctly."""
        data = b"Hello Alasio LZMA! " * 200
        compressed = zstd_compress(memoryview(data), level=level)
        assert zstd_decompress(memoryview(compressed)) == data

    def test_memoryview_slice(self):
        """Memoryview slice of a larger buffer should roundtrip correctly."""
        data = b"prefix" + b"Hello Alasio! " * 100 + b"suffix"
        view = memoryview(data)[6:-6]
        compressed = zstd_compress(view)
        assert zstd_decompress(memoryview(compressed)) == bytes(view)
        assert zstd_decompress(compressed) == b"Hello Alasio! " * 100
