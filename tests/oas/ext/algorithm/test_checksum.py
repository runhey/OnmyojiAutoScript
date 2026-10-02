import hashlib

from oas.ext.algorithm.checksum import checksum_sha1


class TestChecksumSha1Basic:
    """Basic tests for checksum_sha1."""

    def test_single_chunk(self):
        """Single chunk should yield the chunk and then its sha1 digest."""
        data = [b"hello world"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        assert result[-1] == hashlib.sha1(b"hello world").digest()

    def test_multiple_chunks(self):
        """Multiple chunks should be yielded in order, with the final digest
        covering all chunks concatenated."""
        data = [b"hello ", b"world", b"!"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        expected_digest = hashlib.sha1(b"hello world!").digest()
        assert result[-1] == expected_digest

    def test_empty_data(self):
        """Empty input should yield only the sha1 of empty bytes."""
        result = list(checksum_sha1([]))
        assert result == [hashlib.sha1(b"").digest()]

    def test_single_empty_chunk(self):
        """A single empty chunk should yield the empty chunk and its digest."""
        result = list(checksum_sha1([b""]))
        assert result[:-1] == [b""]
        assert result[-1] == hashlib.sha1(b"").digest()

    def test_empty_chunks_among_data(self):
        """Empty chunks in the middle should not affect the rolling checksum."""
        data = [b"abc", b"", b"def"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        expected_digest = hashlib.sha1(b"abcdef").digest()
        assert result[-1] == expected_digest


class TestChecksumSha1LargeData:
    """Tests for checksum_sha1 with larger data."""

    def test_large_chunks(self):
        """A large chunk should be handled correctly."""
        large_chunk = b"a" * 1000000
        result = list(checksum_sha1([large_chunk]))
        assert result[:-1] == [large_chunk]
        assert result[-1] == hashlib.sha1(large_chunk).digest()

    def test_many_small_chunks(self):
        """Many small chunks should be accumulated correctly."""
        chunks = [bytes([i]) for i in range(256)]
        result = list(checksum_sha1(chunks))
        assert result[:-1] == chunks
        expected_digest = hashlib.sha1(bytes(range(256))).digest()
        assert result[-1] == expected_digest


class TestChecksumSha1GeneratorBehavior:
    """Tests for the generator behavior of checksum_sha1."""

    def test_returns_generator(self):
        """checksum_sha1 should return a generator (not a list)."""
        gen = checksum_sha1([b"data"])
        assert hasattr(gen, "__next__")
        assert hasattr(gen, "__iter__")

    def test_lazy_yield(self):
        """Chunks should be yielded as they come, before the final digest."""
        gen = checksum_sha1([b"first", b"second"])
        assert next(gen) == b"first"
        assert next(gen) == b"second"
        assert next(gen) == hashlib.sha1(b"firstsecond").digest()

    def test_binary_data(self):
        """Binary data including null bytes and non-utf8 sequences."""
        data = [b"\x00\x01\x02", b"\xff\xfe\xfd"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        expected_digest = hashlib.sha1(b"\x00\x01\x02\xff\xfe\xfd").digest()
        assert result[-1] == expected_digest


class TestChecksumSha1EdgeCases:
    """Edge case tests for checksum_sha1."""

    def test_single_byte_chunks(self):
        """Each single byte as a separate chunk."""
        data = [b"a", b"b", b"c"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        assert result[-1] == hashlib.sha1(b"abc").digest()

    def test_unicode_bytes(self):
        """UTF-8 encoded unicode data."""
        data = [b"\xe4\xbd\xa0\xe5\xa5\xbd", b"\xe4\xb8\x96\xe7\x95\x8c"]
        result = list(checksum_sha1(data))
        assert result[:-1] == data
        expected_digest = hashlib.sha1(b"\xe4\xbd\xa0\xe5\xa5\xbd\xe4\xb8\x96\xe7\x95\x8c").digest()
        assert result[-1] == expected_digest
