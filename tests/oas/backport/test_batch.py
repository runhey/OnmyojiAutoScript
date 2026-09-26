import pytest

from itertools import batched


class TestBatched:
    def test_batched_normal(self):
        # Normal batching (multiple of n)
        assert list(batched("ABCDEF", 3)) == [("A", "B", "C"), ("D", "E", "F")]
        assert list(batched(range(6), 2)) == [(0, 1), (2, 3), (4, 5)]

    def test_batched_remainder(self):
        # Final batch smaller than n, strict=False (default)
        assert list(batched("ABCDE", 3)) == [("A", "B", "C"), ("D", "E")]
        assert list(batched("ABCDE", 3, strict=False)) == [("A", "B", "C"), ("D", "E")]

    def test_batched_strict_error(self):
        # Final batch smaller than n, strict=True (should raise ValueError)
        with pytest.raises(ValueError, match="batched\\(\\): incomplete batch"):
            list(batched("ABCDE", 3, strict=True))

    def test_batched_strict_success(self):
        # Final batch exactly n, strict=True (should not raise)
        assert list(batched("ABCDEF", 3, strict=True)) == [("A", "B", "C"), ("D", "E", "F")]

    def test_batched_type_error(self):
        # n as non-integer (should raise TypeError)
        with pytest.raises(TypeError):
            list(batched("ABC", "2"))
        with pytest.raises(TypeError):
            list(batched("ABC", 2.0))

    def test_batched_empty(self):
        # Empty iterable
        assert list(batched("", 3)) == []
        assert list(batched([], 3)) == []

    def test_batched_large_n(self):
        # n larger than the iterable length
        assert list(batched("ABC", 10)) == [("A", "B", "C")]

    def test_batched_large_n_strict(self):
        # n larger than the iterable length, strict=True
        with pytest.raises(ValueError, match="batched\\(\\): incomplete batch"):
            list(batched("ABC", 10, strict=True))

    def test_batched_n_1(self):
        # n equal to 1
        assert list(batched("ABC", 1)) == [("A",), ("B",), ("C",)]