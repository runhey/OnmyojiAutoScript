"""
Tests for pathlen_coding: encode_prefix_comb / decode_prefix_comb.
"""
import pytest

from oas.ext.algorithm.pathlen_coding import (
    decode_prefix_comb, decode_suffix_comb, encode_prefix_comb, encode_suffix_comb, prefix_comb_value_check,
    suffix_comb_value_check
)
from oas.ext.algorithm.vlenint import encode_vlenint


class TestPrefixCombValueCheck:
    """Tests for prefix_comb_value_check."""

    def test_valid_inputs(self):
        """Valid inputs should not raise."""
        prefix_comb_value_check([0, 1, 100, 32639], [0, 1, 100, 65535])
        prefix_comb_value_check([], [])
        prefix_comb_value_check([42], [7])

    def test_negative_prefix_reuse(self):
        """Negative prefix_reuse should raise."""
        with pytest.raises(ValueError, match='prefix_reuse must be >= 0'):
            prefix_comb_value_check([-1, 5], [0, 1])

    def test_negative_path_len(self):
        """Negative path_len should raise."""
        with pytest.raises(ValueError, match='path_len must be >= 0'):
            prefix_comb_value_check([0, 5], [-1, 1])

    def test_overflow_prefix_reuse(self):
        """prefix_reuse > 32639 should raise."""
        with pytest.raises(ValueError, match='prefix_reuse must be <= 32639'):
            prefix_comb_value_check([32640], [0])

    def test_overflow_path_len(self):
        """path_len > 65535 should raise."""
        with pytest.raises(ValueError, match='path_len must be <= 65535'):
            prefix_comb_value_check([0], [65536])

    def test_length_mismatch(self):
        """Different length lists should raise."""
        with pytest.raises(ValueError, match='must have same length'):
            prefix_comb_value_check([0, 1], [0])


class TestEncodePrefixCombValueCheck:
    """encode_prefix_comb should reject invalid inputs."""

    def test_length_mismatch(self):
        """Different length lists should raise."""
        with pytest.raises(ValueError, match='same length'):
            encode_prefix_comb([0, 1], [0])

    def test_negative(self):
        """Negative values should raise."""
        with pytest.raises(ValueError, match='>= 0'):
            encode_prefix_comb([-1], [0])

    def test_exceeds_max(self):
        """Values > 65535 should raise."""
        with pytest.raises(ValueError, match='<= 65535'):
            encode_prefix_comb([0], [65536])

    def test_empty(self):
        """Empty lists should produce empty output."""
        result = encode_prefix_comb([], [])
        assert result == []


class TestEncodePrefixCombRoundtrip:
    """Roundtrip encode/decode tests."""

    @pytest.mark.parametrize('pr, pl', [
        ([0], [0]),
        ([0, 0, 0], [0, 0, 0]),
        ([0, 5, 10], [0, 1, 2]),
        ([31], [7]),
        ([32639], [65535]),
        ([0, 1, 2, 3, 4, 5], [0, 0, 0, 0, 0, 0]),
        ([0, 0, 0, 0, 0, 0], [0, 1, 2, 3, 4, 5]),
    ])
    def test_roundtrip_basic(self, pr, pl):
        """Basic roundtrip should recover original values."""
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_roundtrip_systematic_deltas(self):
        """Systematic roundtrip with all diff values from 0 to 80."""
        pr = [0]
        pl = [0]
        for diff in range(1, 81):
            pr.append(pr[-1] + diff)
            pl.append(diff % 256)
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_roundtrip_all_path_lengths(self):
        """Roundtrip every path_len from 0 to 260 (crosses 8 and 256 boundaries)."""
        pr = [0]
        pl = [0]
        for length in range(1, 261):
            pr.append(length)
            pl.append(length)
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_roundtrip_format_boundaries(self):
        """Roundtrip values at each format boundary."""
        pr = [0, 15, 16, 15, 0, 0, 32639, 32638]
        pl = [0, 7, 7, 8, 255, 256, 255, 0]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2
        assert enc[0] < 256
        assert enc[1] < 256
        assert enc[2] < 256
        assert 256 <= enc[3] < 16777216
        assert 256 <= enc[4] < 16777216
        assert enc[5] >= 16777216
        assert 256 <= enc[6] < 16777216
        assert enc[7] < 256

    def test_roundtrip_mixed_zigzag(self):
        """Roundtrip with both positive and negative diffs of various sizes."""
        pr = [5000, 0, 32639, 0, 32639, 25000, 10000]
        pl = [0, 100, 200, 300, 400, 500, 600]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_roundtrip_all_formats(self):
        """Each encoding format must roundtrip correctly."""
        pr = [0, 15, 30, 45, 60, 75, 90]
        pl = [0, 3, 7, 0, 3, 7, 0]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2
        assert all(v < 256 for v in enc), 'Expected all 5b+3b'

        pr = [0, 1000, 2000]
        pl = [0, 200, 255]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2
        assert enc[0] < 256
        assert 256 <= enc[1] < 16777216
        assert 256 <= enc[2] < 16777216

        pr = [0, 32639]
        pl = [0, 40000]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2
        assert enc[0] < 256
        assert enc[1] >= 16777216, 'Expected 2B+2B for pl>=256'


class TestEncodePrefixCombFormat:
    """Verify that the correct encoding format is chosen."""

    def test_5b3b_format(self):
        """When zz<32 and pl<8, output should be < 256."""
        pr = [0]
        pl = [7]
        enc = encode_prefix_comb(pr, pl)
        v = enc[0]
        assert v < 256
        assert v // 8 == 0
        assert v % 8 == 7

    def test_5b3b_max(self):
        """Max 5b+3b value: zz=30, pl=7 -> (30<<3)|7 = 247."""
        pr = [0, 15]
        pl = [0, 7]
        enc = encode_prefix_comb(pr, pl)
        assert enc[1] == 30 * 8 + 7

    def test_1b1b_format(self):
        """When 5b+3b doesn't fit but pl<256, use biased 1B+1B."""
        pr = [0, 16]
        pl = [0, 7]
        enc = encode_prefix_comb(pr, pl)
        v = enc[1]
        assert v == 32 * 256 + 7 + 256
        assert 256 <= v < 16777216

    def test_1b1b_max(self):
        """Max 1B+1B value: zz=65278, pl=255 -> fits just under 2^24."""
        pr = [0, 32639]
        pl = [0, 255]
        enc = encode_prefix_comb(pr, pl)
        assert 256 <= enc[1] < 16777216
        assert enc[1] == 65278 * 256 + 255 + 256

    def test_2b2b_format(self):
        """When pl >= 256, use biased 2B+2B."""
        pr = [0, 100]
        pl = [0, 256]
        enc = encode_prefix_comb(pr, pl)
        assert enc[1] >= 16777216
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

        pr = [0, 32639]
        pl = [0, 65535]
        enc = encode_prefix_comb(pr, pl)
        assert enc[1] >= 16777216
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

    def test_2b2b_max(self):
        """Max 2B+2B value: zz=65278, pl=65535."""
        pr = [0, 32639]
        pl = [0, 65535]
        enc = encode_prefix_comb(pr, pl)
        v = enc[1]
        expected = 16777216 + 65278 * 65536 + 65535
        assert v == expected
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl


class TestDecodePrefixComb:
    """Decode tests for prefix_comb."""

    def test_decode_all(self):
        """Decode consumes all entries from the list."""
        enc = encode_prefix_comb([0, 1, 2], [0, 1, 2])
        pr, pl = decode_prefix_comb(enc)
        assert pr == [0, 1, 2]
        assert pl == [0, 1, 2]

    def test_decode_partial(self):
        """Slice the list to decode fewer entries."""
        enc = encode_prefix_comb([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])
        pr, pl = decode_prefix_comb(enc[:3])
        assert pr == [0, 1, 2]
        assert pl == [0, 1, 2]


class TestEncodePrefixCombEdgeCases:
    """Edge cases."""

    def test_all_zero(self):
        """All zeros should produce all 5b+3b zeros."""
        pr = [0, 0, 0, 0, 0]
        pl = [0, 0, 0, 0, 0]
        enc = encode_prefix_comb(pr, pl)
        assert enc == [0, 0, 0, 0, 0]

    def test_increasing_prefix(self):
        """Monotonically increasing prefix_reuse."""
        pr = [0, 10, 20, 30, 40, 50]
        pl = [0, 1, 2, 3, 4, 5]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_large_jump_then_small(self):
        """Large delta followed by small delta."""
        pr = [0, 5000, 5005]
        pl = [0, 100, 200]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr == pr2
        assert pl == pl2

    def test_boundary_255_256(self):
        """pl=255 vs pl=256 should use different formats."""
        pr = [0, 10]
        pl_255 = [0, 255]
        pl_256 = [0, 256]
        enc_255 = encode_prefix_comb(pr, pl_255)
        enc_256 = encode_prefix_comb(pr, pl_256)
        assert enc_255[1] < 16777216, 'pl=255 should use 1B+1B'
        assert enc_256[1] >= 16777216, 'pl=256 should use 2B+2B'

    def test_boundary_7_8(self):
        """pl=7 vs pl=8 should use different formats."""
        pr = [0, 10]
        pl_7 = [0, 7]
        pl_8 = [0, 8]
        enc_7 = encode_prefix_comb(pr, pl_7)
        enc_8 = encode_prefix_comb(pr, pl_8)
        assert enc_7[1] < 256, 'pl=7 should use 5b+3b'
        assert enc_8[1] >= 256, 'pl=8 should use 1B+1B'


class TestPrefixCombMargins:
    """Marginal inputs at the boundary of the encodable domain."""

    def test_max_prefix_reuse_positive_diff(self):
        """diff = +32639 -> zz = 65278, the largest encodable combined int."""
        pr = [0, 32639]
        pl = [0, 65535]
        enc = encode_prefix_comb(pr, pl)
        assert enc[1] == 16777216 + 65278 * 65536 + 65535
        assert enc[1] < 2 ** 32
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

    def test_max_prefix_reuse_negative_diff(self):
        """diff = -32639 -> zz = 65277, must encode and roundtrip."""
        pr = [32639, 0]
        pl = [0, 65535]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

    def test_prefix_reuse_plus_one_rejected(self):
        """prefix_reuse = 32640 (diff = 32640 -> zz = 65280) must be rejected."""
        with pytest.raises(ValueError, match='prefix_reuse must be <= 32639'):
            prefix_comb_value_check([0, 32640], [0, 0])
        with pytest.raises(ValueError, match='prefix_reuse must be <= 32639'):
            encode_prefix_comb([0, 32640], [0, 0])

    def test_first_value_boundary(self):
        """First diff is relative to 0, so a leading 32639 is the max."""
        enc = encode_prefix_comb([32639], [65535])
        assert enc[0] == 16777216 + 65278 * 65536 + 65535
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == [32639]
        assert pl2 == [65535]
        with pytest.raises(ValueError, match='prefix_reuse must be <= 32639'):
            encode_prefix_comb([32640], [0])

    def test_sawtooth_max(self):
        """Worst-case sawtooth [0, MAX, 0, MAX] must stay encodable."""
        pr = [0, 32639, 0, 32639]
        pl = [0, 65535, 0, 65535]
        enc = encode_prefix_comb(pr, pl)
        assert all(v < 2 ** 32 for v in enc)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

    def test_large_flat_values(self):
        """Large single values with no jumps (diff = 0) must encode."""
        pr = [32639, 32639, 32639]
        pl = [0, 1, 2]
        enc = encode_prefix_comb(pr, pl)
        pr2, pl2 = decode_prefix_comb(enc)
        assert pr2 == pr
        assert pl2 == pl

    def test_all_encodable_fit_vlenint(self):
        """Every value accepted by the checker must fit encode_vlenint (< 2**32)."""
        for pr0, pr1 in [
            (0, 0),
            (0, 1),
            (0, 16384),
            (0, 32639),
            (32639, 0),
            (16384, 32639),
            (32639, 32639),
            (32639, 16384),
        ]:
            for pl in [0, 7, 8, 255, 256, 65535]:
                enc = encode_prefix_comb([pr0, pr1], [0, pl])
                encode_vlenint(enc)  # must not raise
                pr2, pl2 = decode_prefix_comb(enc)
                assert [pr0, pr1] == pr2
                assert [0, pl] == pl2


class TestEncodePrefixCombDeterministic:
    """Same input should produce same output."""

    def test_deterministic(self):
        """Multiple calls with same input should produce same output."""
        pr = [0, 5, 10, 20, 50, 100]
        pl = [0, 1, 2, 3, 4, 5]
        e1 = encode_prefix_comb(pr, pl)
        e2 = encode_prefix_comb(pr, pl)
        assert e1 == e2


class TestEncodePrefixCombLength:
    """Output length should match input length."""

    def test_output_length(self):
        """Output list should have same length as input."""
        for n in [0, 1, 10, 100]:
            pr = list(range(n))
            pl = list(range(n))
            enc = encode_prefix_comb(pr, pl)
            assert len(enc) == n


class TestSuffixCombValueCheck:
    """Tests for suffix_comb_value_check."""

    def test_valid_inputs(self):
        """Valid inputs should not raise."""
        suffix_comb_value_check([0, 1, 65535], [0, 1, 255])
        suffix_comb_value_check([], [])

    def test_negative_reuse(self):
        """Negative suffix_reuse should raise."""
        with pytest.raises(ValueError, match='suffix_reuse must be >= 0'):
            suffix_comb_value_check([-1], [0])

    def test_negative_lookback(self):
        """Negative suffix_lookback should raise."""
        with pytest.raises(ValueError, match='suffix_lookback must be >= 0'):
            suffix_comb_value_check([0], [-1])

    def test_overflow_lookback(self):
        """suffix_lookback > 255 should raise."""
        with pytest.raises(ValueError, match='suffix_lookback must be <= 255'):
            suffix_comb_value_check([0], [256])

    def test_overflow_reuse(self):
        """suffix_reuse > 65535 should raise."""
        with pytest.raises(ValueError, match='suffix_reuse must be <= 65535'):
            suffix_comb_value_check([65536], [0])

    def test_length_mismatch(self):
        """Different length lists should raise."""
        with pytest.raises(ValueError, match='same length'):
            suffix_comb_value_check([0, 1], [0])


class TestSuffixCombRoundtrip:
    """Roundtrip encode/decode tests for suffix_comb."""

    def test_roundtrip_basic(self):
        """Basic roundtrip should recover original values."""
        reuse = [0, 5, 15, 0, 20, 100, 200]
        lb = [0, 3, 15, 0, 10, 50, 255]
        enc = encode_suffix_comb(reuse, lb)
        reuse2, lb2 = decode_suffix_comb(enc)
        assert reuse == reuse2
        assert lb == lb2

    def test_all_zero(self):
        """All zeros should produce all zeros."""
        enc = encode_suffix_comb([0, 0, 0], [0, 0, 0])
        assert enc == [0, 0, 0]

    def test_nibble_format(self):
        """When both < 16, output should be nibble-packed."""
        enc = encode_suffix_comb([5], [3])
        assert enc[0] == 5 * 16 + 3
        assert enc[0] < 256

    def test_fallback_format(self):
        """Fallback format should add +256 bias."""
        enc = encode_suffix_comb([20, 5], [10, 20])
        assert enc[0] == 20 * 256 + 10 + 256
        assert enc[1] == 5 * 256 + 20 + 256

    def test_roundtrip_boundaries(self):
        """Roundtrip at format boundaries."""
        reuse = [0, 15, 16, 0, 65535]
        lb = [0, 15, 0, 16, 255]
        enc = encode_suffix_comb(reuse, lb)
        reuse2, lb2 = decode_suffix_comb(enc)
        assert reuse == reuse2
        assert lb == lb2

    def test_empty(self):
        """Empty lists should produce empty output."""
        assert encode_suffix_comb([], []) == []

    def test_decode_all(self):
        """Decode consumes all entries from encoded list."""
        enc = encode_suffix_comb([0, 1, 2], [0, 1, 2])
        reuse, lb = decode_suffix_comb(enc)
        assert reuse == [0, 1, 2]
        assert lb == [0, 1, 2]

    def test_extra_data_ignored(self):
        """Extra data decoded as additional entries."""
        reuse = [0, 1]
        lb = [0, 1]
        enc = encode_suffix_comb(reuse, lb)
        reuse2, lb2 = decode_suffix_comb(enc)
        assert reuse == reuse2
        assert lb == lb2
