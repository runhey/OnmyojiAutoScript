import pytest

from oas.ext.algorithm.lz77 import match_lz77


class TestMatchLz77NoMatch:
    """Tests for scenarios where no match is found."""

    @pytest.mark.parametrize("data, index, min_length", [
        (b'abcdefghij', 5, 3),        # 'fgh' not in history 'abcde'
        (b'abcabc', 0, 3),            # index=0, no history
        (b'', 0, 3),                  # empty data
        (b'a', 0, 3),                 # data too short
        (b'ab', 1, 3),                # only 1 byte after index
        (b'abc', 2, 3),               # only 1 byte after index
        (b'abcdef', 6, 3),            # index at past-the-end
        (b'abcabc', 2, 3),            # 'cab' not in history 'ab'
    ])
    def test_no_match(self, data, index, min_length):
        """When there's no matching sequence in history, returns (0, 0)."""
        offset, length = match_lz77(memoryview(data), index, min_length=min_length)
        assert offset == 0
        assert length == 0

    def test_no_match_bytearray(self):
        """match_lz77 works with a memoryview wrapping bytearray."""
        offset, length = match_lz77(memoryview(bytearray(b'abcdefghij')), 5)
        assert offset == 0
        assert length == 0


class TestMatchLz77SimpleMatch:
    """Simple match cases with no search refinement needed."""

    @pytest.mark.parametrize("data, index, expected_offset, expected_length", [
        (b'abcabc', 3, 3, 3),         # exact 3-char match at offset 3
        (b'abcdabcd', 4, 4, 4),       # exact 4-char match (min_length=3, curr_len=6>limit_len=4)
        (b'xxabcabc', 5, 3, 3),       # 'abc' found at position 2
        (b'aXa', 2, 2, 1),            # min_length=1, single char match at distance 2
        (b'abXab', 3, 3, 2),          # min_length=1, 'ab' repeats
    ])
    def test_simple_match(self, data, index, expected_offset, expected_length):
        """Basic repetition returns correct offset and length."""
        offset, length = match_lz77(memoryview(data), index, min_length=1)
        assert offset == expected_offset
        assert length == expected_length

    @pytest.mark.parametrize("data_bytes, index, window, min_length, expected", [
        # 1. 剩余长度小于最小匹配长度
        (b"abcdefg", 5, 0, 3, (0, 0)),

        # 2. 完全没有匹配项
        (b"abcdefg", 3, 0, 3, (0, 0)),
        # 3. 标准匹配 (无重叠，全窗口)
        (b"abcdefg_abc", 8, 0, 3, (8, 3)),  # 匹配 "abc"，偏移量为 8
        # 4. 限制窗口大小
        # 匹配 "abc"，但 "abc" 在索引 0，距离为 8。窗口限制为 5，无法匹配。
        (b"abc_def_abc", 8, 5, 3, (0, 0)),
        # 窗口限制为 10，可以匹配
        (b"abc_def_abc", 8, 10, 3, (8, 3)),
        # 5. 滚动复制 (Rolling Copy) 情况
        # 数据 "abcabcabc", index = 3, 理论上可以匹配后续所有字符
        (b"abcabcabc", 3, 0, 3, (3, 6)),
        # 数据 "a" 重复, index = 1
        (b"aaaaaaaaaa", 1, 0, 1, (1, 9)),
        # 6. 二分查找精确微调长度
        # 匹配长度为 5 的 "abcde"
        (b"abcdefg_abcde", 8, 0, 3, (8, 5)),
    ])
    def test_match_lz77_basic_cases(self, data_bytes, index, window, min_length, expected):
        view = memoryview(data_bytes)
        assert match_lz77(view, index, window, min_length) == expected


class TestMatchLz77MultipleCandidates:
    """When multiple match candidates exist, rfind picks the closest one."""

    @pytest.mark.parametrize("data, index, expected_offset", [
        (b'abcabcabc', 6, 3),          # rightmost 'abc' is at position 3
        (b'aaabaaabaaab', 8, 4),       # rightmost match at closest position
    ])
    def test_closest_match(self, data, index, expected_offset):
        """rfind finds the rightmost (closest) occurrence."""
        offset, length = match_lz77(memoryview(data), index)
        assert offset == expected_offset

    def test_match_lz77_long_match_to_the_left(self):
        """
        测试左侧存在更长匹配，而右侧存在较短干扰匹配的情况。
        原算法由于过早限制 limit_len 会在此用例失败，修复后的算法应正确返回最长匹配。
        """
        # 目标是在 index 17 处匹配 "abcdefg"
        # 左侧在 0 处有 "abcdefg" (长度 7)
        # 右侧在 13 处有 "abc" (长度 3)
        data = b"abcdefg______abc_abcdefg"
        view = memoryview(data)

        # 修复后的算法应该越过右侧的短匹配，正确找到左侧长度为 7 的匹配
        offset, length = match_lz77(view, index=17, window=0, min_length=3)
        assert length == 7
        assert offset == 17  # 17 - 0 = 17

    def test_match_lz77_exact_window_boundary(self):
        """测试刚好处于窗口边界的匹配"""
        # "abc" 在索引 0，index 在 5。距离为 5。
        # 如果 window = 5，应该刚好能匹配到。
        # 如果 window = 4，则无法匹配到。
        data = b"abc__abc"
        view = memoryview(data)
        assert match_lz77(view, index=5, window=5, min_length=3) == (5, 3)
        assert match_lz77(view, index=5, window=4, min_length=3) == (0, 0)


class TestMatchLz77ExponentialGrowth:
    """The exponential growth phase finds increasingly long matches."""

    def test_exponential_single_doubling(self):
        """Match found at min_length*2 after one doubling."""
        # "abcdef" repeats after 6 chars, offset=6
        # index=6, min_length=3
        # target=data[6:9]=b'abc', rfind in history[0:6]=b'abcdef' finds at 0
        # best_len=3, best_idx=0
        # limit_len = min(6, len(data)-6=12) = 6
        # curr_len=6, target=data[6:12]=b'abcdef', rfind obj[0:6]=b'abcdef' at 0 ✓
        # best_len=6, best_idx=0
        # curr_len=12 > limit_len=6, skip
        data = memoryview(b'abcdefabcdefghij')
        offset, length = match_lz77(data, 6)
        assert offset == 6
        assert length == 6

    def test_exponential_two_doublings(self):
        """Match found at min_length*4 after two successful doublings."""
        # "abcdefgh" repeats after 8, offset=8
        # index=8, the pattern is 8 chars long
        # exponential: 6 -> success, 12 -> exceeds limit_len=8
        data = memoryview(b'abcdefghabcdefghijklmnop')
        offset, length = match_lz77(data, 8)
        assert offset == 8
        assert length == 8

    def test_exponential_then_curr_len_hits_limit(self):
        """Exponential doubles until curr_len exceeds limit_len."""
        # The match length is bounded by limit_len, not by match failure
        data = memoryview(b'ABCABCABC')
        # index=3, history='ABC', target from 3 = 'ABC'
        # best_len=3, best_idx=0
        # limit_len = min(3, 6) = 3
        # curr_len=6 > limit_len=3, skip exponential
        # binary: low=4 > high=3, skip.
        # offset=3 == best_len=3, rolling copy extends to max_length=6
        # Returns (3, 6)
        offset, length = match_lz77(memoryview(data), 3)
        assert offset == 3
        assert length == 6


class TestMatchLz77BinarySearch:
    """Binary search fine-tunes match length after exponential phase."""

    def test_binary_search_finds_longer(self):
        """Binary search finds a match length between best_len+1 and curr_len-1."""
        # "ABCDEFGHIJ" repeats at offset 10, but at position 10 only the first 8 chars
        # match (the 9th char differs).
        #   data: A B C D E F G H I J A B C D E F G H X Y
        #         0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9
        #                                ^ index=10
        # target at 10: 'ABCDEFGH', 'I' at 18 vs 'X' at index 18
        # min_length=3 exponential finds at 6 (ABCDEF)
        # then curr_len=12 > limit_len, skip
        # binary searches [7, limit_len=10], finds max 8
        data = memoryview(b'ABCDEFGHIJABCDEFGHXY')
        offset, length = match_lz77(data, 10)
        assert offset == 10
        assert length == 8

    def test_binary_search_exact_limit(self):
        """Binary search matches up to the full limit_len."""
        # The match extends exactly to the boundary
        data = memoryview(b'0123456789abc0123456789xyz')
        # index=13, history='0123456789abc'
        # data[13:]=b'0123456789xyz', only first 10 match (until 'xyz' vs 'abc')
        offset, length = match_lz77(memoryview(data), 13)
        assert offset == 13
        assert length == 10


class TestMatchLz77RollingCopy:
    """Rolling copy detection (offset == length)."""

    def test_rolling_copy_simple(self):
        """When offset equals current best_len, extend via rolling copy."""
        # "abcabcabc" - the classic LZ77 rolling copy case
        # index=3, best_len=3, offset=3
        # Since offset==best_len, rolling copy extends: copy 'abc' repeatedly
        data = memoryview(b'abcabcabcabc')
        offset, length = match_lz77(data, 3)
        # rolling: abc|abc|abc|abc  -> extends to 9
        # But wait: max_length=9, so best_len extends from 3 to 9
        assert offset == 3
        assert length == 9

    def test_rolling_copy_long(self):
        """Rolling copy extends across many repetitions."""
        data = memoryview(b'ab' * 20)
        offset, length = match_lz77(data, 4)
        # index=4, target=data[4:7]=b'aba', rfind in [0,4)=b'abab' finds at 0
        # best_len=3, best_idx=0, limit_len=min(4,36)=4
        # curr_len=6 > 4, skip exponential
        # binary: mid=4, finds b'abab' in obj[0:4], best_len=4
        # offset=4, best_len=4, offset==best_len, rolling copy to max_length=36
        assert offset == 4
        assert length == 36

    def test_rolling_copy_with_prior_extend(self):
        """Exponential phase extends then rolling copy finishes."""
        # Longer initial pattern with rolling tail
        # "abcd" repeats: exponential finds length 4 at offset 4
        # Then offset (4) == best_len (4), rolling copy kicks in
        data = memoryview(b'abcdabcdabcdabcd')
        offset, length = match_lz77(data, 4)
        # max_length = 12
        # exponential: curr_len=6 > limit_len=4, skip
        # binary: low=4, high=min(5,4)=4. low>high, skip.
        # offset=4, best_len=4, offset==best_len -> rolling
        # extends from 4 to 12
        assert offset == 4
        assert length == 12

    def test_rolling_copy_stops_at_data_end(self):
        """Rolling copy stops when the data ends."""
        data = memoryview(b'xxx')
        offset, length = match_lz77(data, 0)
        # index=0, no history, so (0, 0)
        assert offset == 0
        assert length == 0

    def test_rolling_copy_non_rolling(self):
        """When offset != best_len, rolling copy is not triggered."""
        # Even though there's repetition, it's not a rolling pattern
        data = memoryview(b'abcdeXabcde')
        # index=6, match 'abcde' at offset=6, best_len=5
        # limit_len = min(6, 5) = 5, so curr_len=6 > limit_len
        # binary: low=4, high=min(5,5)=5
        # mid=4, target=data[6:10]=b'abcde'... wait
        offset, length = match_lz77(memoryview(data), 6)
        # offset=6, best_len=5
        # offset(6) != best_len(5), so no rolling copy
        assert offset == 6
        assert length == 5


class TestMatchLz77Window:
    """Window parameter restricts the search range."""

    def test_window_zero_full_history(self):
        """window=0 searches the full history."""
        data = memoryview(b'xxxxabcabc')
        # index=7, full search in [0,7)
        # rfind(b'abc', 0, 7) in b'xxxxabc' finds at 4
        offset, length = match_lz77(data, 7, window=0)
        assert offset == 3
        assert length == 3

    def test_window_restricts_range(self):
        """Small window excludes distant matches."""
        data = memoryview(b'abcdeabcde')
        # index=5, window=2 -> search in [3,5)
        # obj[3:5] = b'de', 'abc' not found
        offset, length = match_lz77(data, 5, window=2)
        assert offset == 0
        assert length == 0

    def test_window_finds_match_in_range(self):
        """Match found within window limits."""
        data = memoryview(b'xxxxabcabc')
        # index=7, window=4 -> search in [3,7)
        # obj[3:7] = b'xabc', rfind(b'abc', 3, 7) finds at 4
        offset, length = match_lz77(data, 7, window=4)
        assert offset == 3
        assert length == 3

    @pytest.mark.parametrize("window", [1, 2, 3])
    def test_window_too_small(self, window):
        """Window smaller than min_length prevents any match."""
        data = memoryview(b'aaaabbbb')
        # index=4, search in [4-window, 4)
        # No 'aaaa' (4 chars) can fit in window < 4
        offset, length = match_lz77(data, 4, window=window)
        # With min_length=3, window=3 gives search in [1,4)
        # obj[1:4] = b'aaa', target = data[4:7] = b'bbb'
        # No match
        assert offset == 0
        assert length == 0

    def test_window_clamped_to_zero(self):
        """Negative start from window is clamped to 0."""
        data = memoryview(b'abcabc')
        # index=1, window=5 -> start would be -4, clamped to 0
        # Same as full search
        offset, length = match_lz77(data, 1, window=5)
        # No match at index=1 since only 'a' is before, 'bc' after
        # But wait: min_length=3, max_length=5 >= 3
        # target = data[1:4] = b'bca'
        # search obj[0:1] = b'a' for b'bca' -> not found
        assert offset == 0
        assert length == 0


class TestMatchLz77MinLength:
    """Custom min_length parameter."""

    def test_min_length_1_short_match(self):
        """With min_length=1, a single matching byte is found."""
        data = memoryview(b'abca')
        # index=3, target=b'a', rfind in [0,3)=b'abc' at 0
        # min_length=1, best_len=1
        # limit_len = min(3, 1) = 1
        # curr_len=2 > limit_len, skip exponential
        # binary: low=2, high=min(1,1)=1 -> skip
        # offset=3 != best_len=1, no rolling
        offset, length = match_lz77(data, 3, min_length=1)
        assert offset == 3
        assert length == 1

    def test_min_length_1_longer_match(self):
        """With min_length=1, exponential + binary finds longer match."""
        data = memoryview(b'abcXabc')
        # index=4, target=data[4:5]=b'a', rfind in [0,4)=b'abcX' at 0
        # best_len=1, best_idx=0, limit_len = min(4, 3) = 3
        # curr_len=2, finds b'ab' in obj[0:2], best_len=2, best_idx=0
        # curr_len=4 > limit_len=3, skip exponential
        # binary low=3, high=3: finds b'abc' in obj[0:3], best_len=3
        # offset=4, best_len=3, no rolling copy
        offset, length = match_lz77(data, 4, min_length=1)
        assert offset == 4
        assert length == 3

    def test_min_length_5(self):
        """High min_length requires longer match."""
        data = memoryview(b'abcdefghijabcdefghij')
        # index=10, min_length=5
        # target=data[10:15]=b'abcde', rfind in [0,10) at 0
        # best_len=5, best_idx=0
        # limit_len = min(10, 10) = 10
        # curr_len=10, target=data[10:20]=b'abcdefghij', search in obj[0:10]=b'abcdefghij'
        # rfind finds at 0, best_len=10
        # Returns (10, 10)
        offset, length = match_lz77(data, 10, min_length=5)
        assert offset == 10
        assert length == 10

    def test_min_length_too_high(self):
        """min_length larger than remaining data returns (0, 0)."""
        data = memoryview(b'abc')
        offset, length = match_lz77(data, 1, min_length=4)
        assert offset == 0
        assert length == 0


class TestMatchLz77EdgeCases:
    """Edge cases and boundary conditions."""

    def test_index_at_element_boundary(self):
        """Index at a byte value boundary."""
        data = memoryview(b'\x00\x01\x02\x00\x01\x02')
        offset, length = match_lz77(data, 3)
        assert offset == 3
        assert length == 3

    def test_match_with_null_bytes(self):
        """Binary data with null bytes works correctly."""
        data = memoryview(b'\x00\x00\x00\x00\x00\x00')
        offset, length = match_lz77(data, 3)
        # target = data[3:6] = b'\x00\x00\x00'
        # rfind in obj[0:3] = b'\x00\x00\x00' at position 0
        # best_len=3, best_idx=0
        # limit_len = min(3, 3) = 3
        # curr_len=6 > limit_len, skip exponential
        # binary: low=4, high=min(5,3)=3. skip
        # offset=3 == best_len=3, rolling copy
        # extends to max_length=3, so best_len=3
        assert offset == 3
        assert length == 3

    def test_match_near_very_end(self):
        """Match when there's just enough data for min_length."""
        data = memoryview(b'abXab')
        # len=5, index=3, target=data[3:5]=b'ab', max_length=2
        # max_length=2 < min_length=3, returns (0, 0)
        offset, length = match_lz77(data, 3)
        assert offset == 0
        assert length == 0

    def test_multiple_matches_rfind_picks_rightmost(self):
        """When there are multiple matches, rfind picks the rightmost one."""
        data = memoryview(b'aXaYa')
        # index=4, min_length=1
        # target = data[4:5] = b'a'
        # rfind in obj[0:4]=b'aXaY' -> finds at position 2 (the 'a' at pos 2, not 0)
        # The match at distance 2 is preferred over distance 4
        offset, length = match_lz77(data, 4, min_length=1)
        assert offset == 2
        assert length == 1

    def test_long_binary_data(self):
        """Longer binary data works correctly."""
        data = memoryview(bytes(range(256)) * 2)
        offset, length = match_lz77(data, 256)
        # Full 256 bytes should match
        assert offset == 256
        assert length == 256

    def test_rolling_copy_with_null_bytes(self):
        """Rolling copy detection works with binary data containing null bytes."""
        data = memoryview(b'\x00\x01\x02' * 10)
        offset, length = match_lz77(data, 3)
        # Rolling copy of 3-byte pattern
        assert offset == 3
        assert length == 27


class TestMatchLz77MaxLength:
    """Tests for the max_length parameter that caps the maximum copy length."""

    # ── simple match capped ──────────────────────────────────────────────

    def test_max_length_caps_simple_match(self):
        """max_length shorter than the natural match length should cap it."""
        # "abcdef" repeats at offset 6; natural match length = 6
        data = memoryview(b'abcdefabcdef')
        offset, length = match_lz77(data, 6, max_length=4)
        assert offset == 6
        assert length == 4, f"Expected 4, got {length}"

    def test_max_length_larger_than_natural(self):
        """max_length larger than the natural match has no effect."""
        data = memoryview(b'abcdefabcdef')
        offset, length = match_lz77(data, 6, max_length=100)
        assert offset == 6
        assert length == 6, f"Expected 6, got {length}"

    # ── rolling copy capped ──────────────────────────────────────────────

    def test_max_length_caps_rolling_copy(self):
        """Rolling copy must not exceed max_length."""
        data = memoryview(b'abc' * 10)           # 30 bytes
        offset, length = match_lz77(data, 3, max_length=7)
        # natural rolling would reach 27, but capped at 7
        assert offset == 3
        assert length == 7, f"Expected 7, got {length}"

    def test_max_length_caps_rolling_copy_exact(self):
        """Rolling copy stops exactly at max_length boundary."""
        data = memoryview(b'ab' * 20)            # 40 bytes
        offset, length = match_lz77(data, 4, max_length=10)
        # natural rolling reaches 36, capped at 10
        assert offset == 4
        assert length == 10, f"Expected 10, got {length}"

    def test_max_length_one_above_min_length(self):
        """max_length just above min_length allows rolling to extend a bit."""
        # Use data with plenty of room after index so max_length is the binding cap
        data = memoryview(b'abc' * 10)           # 30 bytes
        offset, length = match_lz77(data, 3, max_length=4, min_length=3)
        # natural rolling would reach 27, but capped at 4
        assert offset == 3
        assert length == 4, f"Expected 4, got {length}"

    # ── binary search capped ─────────────────────────────────────────────

    def test_max_length_caps_binary_search(self):
        """Binary search phase must not exceed max_length."""
        # "ABCDEFGHIJ" repeats at offset 10, natural match = 8
        data = memoryview(b'ABCDEFGHIJABCDEFGHXY')
        offset, length = match_lz77(data, 10, max_length=5)
        assert offset == 10
        assert length == 5, f"Expected 5, got {length}"

    def test_max_length_caps_exponential_then_binary(self):
        """Exponential + binary search both capped by max_length."""
        data = memoryview(b'abcdefghijklmnopqrstabcdefghijklmnopqrst')
        # index=20, natural match on all 20 chars
        offset, length = match_lz77(data, 20, max_length=8)
        assert offset == 20
        assert length == 8, f"Expected 8, got {length}"

    # ── zero / no-limit ──────────────────────────────────────────────────

    def test_max_length_zero_no_limit(self):
        """max_length=0 (default) imposes no limit."""
        data = memoryview(b'abc' * 10)
        offset, length = match_lz77(data, 3)
        assert offset == 3
        assert length == 27, f"Expected 27 (no limit), got {length}"

    # ── below min_length ─────────────────────────────────────────────────

    def test_max_length_below_min_length_returns_no_match(self):
        """When max_length < min_length, no match is possible."""
        data = memoryview(b'abcabc')
        offset, length = match_lz77(data, 3, max_length=2)
        assert offset == 0
        assert length == 0

    def test_max_length_equal_min_length(self):
        """max_length == min_length allows exactly a min_length match."""
        data = memoryview(b'abcabc')
        offset, length = match_lz77(data, 3, max_length=3)
        assert offset == 3
        assert length == 3, f"Expected 3, got {length}"

    # ── with window ─────────────────────────────────────────────────────

    def test_max_length_with_window(self):
        """max_length and window work together: the tighter bound wins."""
        # "abc" at offset 0, index=8, window=8 allows the match
        # avail=7, max_length=3 caps the match tighter than avail
        data = memoryview(b'abc_123_abc456')
        offset, length = match_lz77(data, 8, window=8, max_length=3)
        assert offset == 8, f"Expected offset 8, got {offset}"
        assert length == 3, f"Expected length 3, got {length}"

    # ── invariant with max_length ────────────────────────────────────────

    @pytest.mark.parametrize("data_bytes, index, max_len", [
        (b'abcabc', 3, 3),
        (b'abcabc', 3, 4),
        (b'abcabc', 3, 5),
        (b'abcdefabcdef', 6, 4),
        (b'abcdefabcdef', 6, 5),
        (b'ab' * 10, 4, 6),
        (b'ab' * 10, 4, 10),
        (b'abc' * 10, 3, 8),
        (b'ABCDEFGHIJABCDEFGHXY', 10, 6),
        (b'ABCDEFGHIJABCDEFGHXY', 10, 9),
        (b'abc_abc_abc', 4, 3),
        (b'\x00\x01\x02\x00\x01\x02', 3, 2),
    ])
    def test_max_length_invariant(self, data_bytes, index, max_len):
        """With max_length set, the invariant holds AND length never exceeds max_len."""
        data = memoryview(data_bytes)
        offset, length = match_lz77(data, index, max_length=max_len)
        # length must never exceed max_len
        assert length <= max_len, \
            f"length ({length}) exceeds max_length ({max_len})"
        if length > 0:
            match = data[index - offset: index - offset + length]
            target = data[index: index + length]
            assert match == target, \
                f"Invariant failed with max_length={max_len}"
            assert offset > 0
            assert index - offset >= 0

    # ── stress: many random-like patterns ──────────────────────────────

    @pytest.mark.parametrize("pattern, repeat, index, max_len", [
        (b'abc', 12, 3, 5),
        (b'abc', 12, 3, 10),
        (b'abc', 12, 3, 15),
        (b'xyz', 8, 3, 4),
        (b'xyz', 8, 3, 12),
        (b'\x00\x01\x02', 10, 3, 6),
        (b'\x00\x01\x02', 10, 3, 20),
    ])
    def test_max_length_rolling_stress(self, pattern, repeat, index, max_len):
        """Rolling copy with various max_length values never exceeds the cap."""
        data = memoryview(pattern * repeat)
        offset, length = match_lz77(data, index, max_length=max_len)
        assert length <= max_len, \
            f"Rolling copy exceeded max_length: {length} > {max_len}"
        if length > 0:
            match = data[index - offset: index - offset + length]
            target = data[index: index + length]
            assert match == target


class TestMatchLz77Property:
    """Property-like tests that verify the match invariant."""

    @pytest.mark.parametrize("data_bytes, index", [
        (b'abcabc', 3),
        (b'abcdefabcdef', 6),
        (b'aaaaaa', 3),
        (b'abcdeXabcde', 6),
        (b'ABCDEFGHIJABCDEFGHXY', 10),
        (b'test_data_test_data', 9),
        (b'ab' * 10, 4),
        (b'\x00\x01\x02\x00\x01\x02', 3),
    ])
    def test_match_invariant(self, data_bytes, index):
        """The returned (offset, length) must satisfy the LZ77 match invariant."""
        data = memoryview(data_bytes)
        offset, length = match_lz77(data, index)
        if length > 0:
            match = data[index - offset: index - offset + length]
            target = data[index: index + length]
            assert match == target, \
                f"Invariant failed: data[{index}-{offset}:{index}-{offset}+{length}] != data[{index}:{index}+{length}]"
            assert offset > 0, "Offset must be positive for a non-zero match"
            assert length >= 3, f"Length must be >= min_length (3), got {length}"
            assert index - offset >= 0, "Match must be in history (before index)"

    def test_match_longer_than_history(self):
        """Rolling copy can produce matches longer than the available history."""
        data = memoryview(b'abc' * 10)
        index = 5
        offset, length = match_lz77(data, index)
        # index=5, data = b'abcabcabcabcabcabcabcabcabcabc' (30 bytes)
        # index=5: ...abcab|cabc...
        # data[5:8] = b'cab', search in obj[0:5] = b'abcab'
        # rfind(b'cab', 0, 5): obj[2:5]=b'cab' at 2
        # best_len=3, best_idx=2
        # limit_len = min(3, 25) = 3
        # curr_len=6 > limit_len=3, skip
        # offset=5-2=3, best_len=3, offset==best_len, rolling!
        # extends to max_length=25
        assert offset == 3
        assert length == 25
        # Verify invariant
        match = data[index - offset: index - offset + length]
        target = data[index: index + length]
        assert match == target
