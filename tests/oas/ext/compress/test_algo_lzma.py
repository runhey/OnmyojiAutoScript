import pytest

from oas.ext.compress.algo_lzma import _lzma_dictsize, lzma_compress, lzma_decompress


class TestLzmaDictsize:
    """Tests for _lzma_dictsize function."""

    @pytest.mark.parametrize("length, expected", [
        # Boundary: 0 and min
        pytest.param(0, 4096, id="zero"),
        pytest.param(1, 4096, id="single-byte"),
        pytest.param(4095, 4096, id="just-below-4k"),
        pytest.param(4096, 4096, id="exactly-4k"),
        # Powers of 2
        pytest.param(4097, 8192, id="just-above-4k"),
        pytest.param(8192, 8192, id="exactly-8k"),
        pytest.param(8193, 16384, id="just-above-8k"),
        pytest.param(16384, 16384, id="exactly-16k"),
        pytest.param(16385, 32768, id="just-above-16k"),
        pytest.param(32768, 32768, id="exactly-32k"),
        pytest.param(32769, 65536, id="just-above-32k"),
        pytest.param(65536, 65536, id="exactly-64k"),
        pytest.param(65537, 131072, id="just-above-64k"),
        pytest.param(131072, 131072, id="exactly-128k"),
        pytest.param(131073, 262144, id="just-above-128k"),
        pytest.param(262144, 262144, id="exactly-256k"),
        pytest.param(262145, 524288, id="just-above-256k"),
        pytest.param(524288, 524288, id="exactly-512k"),
        pytest.param(524289, 1048576, id="just-above-512k"),
        pytest.param(1048576, 1048576, id="exactly-1m"),
        pytest.param(1048577, 2097152, id="just-above-1m"),
        pytest.param(2097152, 2097152, id="exactly-2m"),
        pytest.param(2097153, 4194304, id="just-above-2m"),
        pytest.param(4194304, 4194304, id="exactly-4m"),
        pytest.param(4194305, 8388608, id="just-above-4m"),
        pytest.param(8388608, 8388608, id="exactly-8m"),
        pytest.param(8388609, 16777216, id="just-above-8m"),
        pytest.param(16777216, 16777216, id="exactly-16m"),
        pytest.param(16777217, 33554432, id="just-above-16m"),
        pytest.param(33554432, 33554432, id="exactly-32m"),
        pytest.param(33554433, 67108864, id="just-above-32m"),
        # Max
        pytest.param(67108864, 67108864, id="exactly-64m"),
        pytest.param(67108865, 67108864, id="just-above-64m"),
        pytest.param(100000000, 67108864, id="large"),
    ])
    def test_no_cap(self, length, expected):
        """Without max_dict_size, should choose smallest power of 2 >= length."""
        assert _lzma_dictsize(length) == expected

    @pytest.mark.parametrize("length, max_dict_size, expected", [
        # max_dict_size < 4096 → cap to 4096
        pytest.param(5000, 0, 4096, id="cap-zero"),
        pytest.param(5000, 1, 4096, id="cap-one"),
        pytest.param(5000, 100, 4096, id="cap-small"),
        pytest.param(5000, 4095, 4096, id="cap-4095"),
        # max_dict_size = 4096 (power of 2)
        pytest.param(5000, 4096, 4096, id="cap-4k-power-of-2"),
        # max_dict_size not power of 2 → floor to nearest
        pytest.param(5000, 4097, 4096, id="cap-4097-floor-4k"),
        pytest.param(5000, 5000, 4096, id="cap-5000-floor-4k"),
        pytest.param(5000, 8191, 4096, id="cap-8191-floor-4k"),
        pytest.param(5000, 8192, 8192, id="cap-8k-power-of-2"),
        pytest.param(5000, 10000, 8192, id="cap-10000-floor-8k"),
        pytest.param(40000, 50000, 32768, id="cap-50000-floor-32768"),
        # max_dict_size power of 2
        pytest.param(40000, 65536, 65536, id="cap-65536-power-of-2"),
        pytest.param(100000, 65536, 65536, id="cap-65536-capped"),
        pytest.param(100000, 131072, 131072, id="cap-131072-power-of-2"),
        # max_dict_size exceeding 64MB → still cap at 64MB
        pytest.param(100000000, 134217728, 67108864, id="cap-above-64m"),
        # max_dict_size below data size
        pytest.param(1000000, 8192, 8192, id="data-exceeds-cap"),
        # max_dict_size = None → no cap
        pytest.param(5000, None, 8192, id="no-cap"),
    ])
    def test_with_cap(self, length, max_dict_size, expected):
        """With max_dict_size, should cap at nearest power of 2."""
        assert _lzma_dictsize(length, max_dict_size=max_dict_size) == expected


class TestLzmaCompress:
    """Tests for lzma_compress function."""

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"a", id="single-byte"),
        pytest.param(b"Hello Alasio!", id="short"),
        pytest.param(b"Hello Alasio! " * 100, id="medium"),
        pytest.param(b"Hello Alasio LZMA! " * 5000, id="large"),
        pytest.param(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 50, id="all-byte-values"),
        pytest.param("Hello, 世界! ".encode("utf-8") * 50, id="unicode"),
        pytest.param(b"A" * 100000, id="highly-compressible"),
    ])
    def test_compress_decompress_roundtrip(self, data):
        """Compress then decompress should return original data."""
        compressed = lzma_compress(data)
        decompressed = lzma_decompress(compressed)
        assert decompressed == data

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"a", id="single"),
        pytest.param(b"ab", id="two-bytes"),
        pytest.param(b"Hello", id="short-string"),
    ])
    def test_small_data_roundtrip(self, data):
        """Small data should survive roundtrip."""
        compressed = lzma_compress(data)
        decompressed = lzma_decompress(compressed)
        assert decompressed == data

    @pytest.mark.parametrize("max_dict_size", [
        pytest.param(None, id="no-cap"),
        pytest.param(4096, id="4k"),
        pytest.param(65536, id="64k"),
        pytest.param(1048576, id="1m"),
        pytest.param(67108864, id="64m"),
        pytest.param(50000, id="not-power-of-2"),
    ])
    def test_with_max_dict_size(self, max_dict_size):
        """Compress with max_dict_size should roundtrip correctly."""
        data = b"Hello Alasio LZMA! " * 200
        compressed = lzma_compress(data, max_dict_size=max_dict_size)
        decompressed = lzma_decompress(compressed)
        assert decompressed == data

    def test_compress_less_than_raw(self):
        """Compression should reduce size for compressible data."""
        data = b"Hello Alasio LZMA! " * 5000
        compressed = lzma_compress(data)
        # LZMA with preset 9 should compress this well
        assert len(compressed) < len(data)

    def test_multiple_operations(self):
        """Multiple compress/decompress operations should not interfere."""
        datasets = [
            b"First dataset with repeated content. " * 50,
            b"Second dataset with different repeated content. " * 50,
            b"Third dataset, completely different. " * 50,
        ]
        for data in datasets:
            compressed = lzma_compress(data)
            decompressed = lzma_decompress(compressed)
            assert decompressed == data


class TestLzmaMemoryview:
    """Tests for memoryview input support in compress and decompress."""

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"Hello Alasio!", id="short"),
        pytest.param(b"Hello Alasio LZMA! " * 500, id="medium"),
        pytest.param(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 50, id="all-byte-values"),
        pytest.param(b"A" * 100000, id="highly-compressible"),
    ])
    def test_compress_memoryview(self, data):
        """Compress should accept memoryview input."""
        compressed = lzma_compress(memoryview(data))
        assert lzma_decompress(compressed) == data

    @pytest.mark.parametrize("data", [
        pytest.param(b"", id="empty"),
        pytest.param(b"Hello Alasio!", id="short"),
        pytest.param(b"Hello Alasio LZMA! " * 500, id="medium"),
        pytest.param(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc" * 50, id="all-byte-values"),
    ])
    def test_decompress_memoryview(self, data):
        """Decompress should accept memoryview input."""
        compressed = lzma_compress(data)
        assert lzma_decompress(memoryview(compressed)) == data

    @pytest.mark.parametrize("max_dict_size", [
        pytest.param(None, id="no-cap"),
        pytest.param(65536, id="64k"),
        pytest.param(50000, id="not-power-of-2"),
    ])
    def test_memoryview_with_max_dict_size(self, max_dict_size):
        """Compress memoryview with max_dict_size should roundtrip correctly."""
        data = b"Hello Alasio LZMA! " * 200
        compressed = lzma_compress(memoryview(data), max_dict_size=max_dict_size)
        assert lzma_decompress(memoryview(compressed)) == data

    def test_memoryview_slice(self):
        """Memoryview slice of a larger buffer should roundtrip correctly."""
        data = b"prefix" + b"Hello Alasio LZMA! " * 100 + b"suffix"
        view = memoryview(data)[6:-6]
        compressed = lzma_compress(view)
        assert lzma_decompress(memoryview(compressed)) == bytes(view)
        assert lzma_decompress(compressed) == b"Hello Alasio LZMA! " * 100
