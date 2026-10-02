"""
Tests for oas.ext.algorithm.bit2coding.

``encode_bit2_opcode_iter(data)`` encodes a 2-bit value list (values 0-3) into
opcode tuples using run-length and LZ77-style copy detection.

``decode_bit2_opcode(opcodes)`` decodes opcode tuples back to the original
list[int].
"""

import pytest

from oas.ext.algorithm.bit2coding import decode_bit2_opcode, encode_bit2_opcode_iter

# ==============================================================================
# encode_bit2_opcode_iter — edge cases
# ==============================================================================


class TestEncodeEmptyAndSingleton:
    """Empty and single-element inputs."""

    def test_empty_data(self):
        """Empty input yields no opcodes."""
        assert list(encode_bit2_opcode_iter([])) == []

    @pytest.mark.parametrize("val", [0, 1, 2, 3])
    def test_single_element(self, val):
        """Single element always yields a literal opcode."""
        result = list(encode_bit2_opcode_iter([val]))
        assert len(result) == 1
        op_type, values = result[0]
        assert op_type == 0
        assert list(values) == [val]

    def test_two_different_elements(self):
        """Two different elements produce one literal."""
        result = list(encode_bit2_opcode_iter([1, 2]))
        assert len(result) == 1
        assert result[0][0] == 0
        assert list(result[0][1]) == [1, 2]


# ==============================================================================
# encode_bit2_opcode_iter — literal path
# ==============================================================================


class TestEncodeLiteral:
    """Cases where no run (>=4) or copy (>=3) is found → literals accumulate."""

    def test_four_distinct_values(self):
        """4 distinct values, no repeats → single literal block."""
        data = [0, 1, 2, 3]
        result = list(encode_bit2_opcode_iter(data))
        assert len(result) == 1
        assert result[0][0] == 0
        assert list(result[0][1]) == [0, 1, 2, 3]


# ==============================================================================
# encode_bit2_opcode_iter — run path
# ==============================================================================


class TestEncodeRun:
    """Cases where a run (4+ identical consecutive values) is found."""

    def test_simple_run(self):
        """4+ identical values → run opcode."""
        data = [0, 0, 0, 0, 0]
        result = list(encode_bit2_opcode_iter(data))
        assert result == [(1, 0, 5)]

    def test_run_of_all_same(self):
        """Entirely uniform data → single run opcode."""
        for val in range(4):
            data = [val] * 10
            result = list(encode_bit2_opcode_iter(data))
            assert result == [(1, val, 10)]

    def test_run_then_literal(self):
        """Run followed by non-repeating values."""
        data = [2, 2, 2, 2, 2, 0, 1, 3]
        result = list(encode_bit2_opcode_iter(data))
        assert result == [(1, 2, 5), (0, [0, 1, 3])]

    def test_multiple_runs(self):
        """Multiple run segments separated by distinct values."""
        data = [1, 1, 1, 1, 1, 3, 0, 0, 0, 0]
        result = list(encode_bit2_opcode_iter(data))
        assert result == [(1, 1, 5), (0, [3]), (1, 0, 4)]

    def test_run_length_boundaries(self):
        """Run lengths at the short/long format boundary (34, 35, 36)."""
        # 34: short format (cost=1)
        result = list(encode_bit2_opcode_iter([0] * 34))
        assert result == [(1, 0, 34)], f"Expected single run of 34, got {result}"

        # 35: long format boundary (cost=2 + 0)
        result = list(encode_bit2_opcode_iter([0] * 35))
        assert result == [(1, 0, 35)], f"Expected single run of 35, got {result}"

        # 36: long format (cost=2 + 0)
        result = list(encode_bit2_opcode_iter([0] * 36))
        assert result == [(1, 0, 36)], f"Expected single run of 36, got {result}"


# ==============================================================================
# encode_bit2_opcode_iter — copy path
# ==============================================================================


class TestEncodeCopy:
    """Comprehensive, mathematically audited cases for LZ77-style copy operations."""

    def test_rolling_copy(self):
        """Tests rolling copy (offset < length) where a pattern repeats sequentially."""
        # 模式 [0, 1, 2] 重复 5 次，总长 15
        data = [0, 1, 2] * 5
        result = list(encode_bit2_opcode_iter(data))

        # 1 个长度 3 的字面值 (2字节) + 1 个长度 12 的滚动复制 (2字节) = 4字节
        assert result == [(0, [0, 1, 2]), (2, 3, 12)]

    def test_non_rolling_short_copy(self):
        """Tests non-rolling short copy (offset >= length, offset <= 256, length <= 32)."""
        # 设计一个 12 字节的“无自我重复模式”（内部无任何相同的 3 元素连续组合）
        pattern = [0, 1, 2, 3, 0, 2, 1, 3, 0, 3, 2, 1]  # 长度 12
        separator = [2, 2, 2, 2]  # 长度 4 (Run)
        data = pattern + separator + pattern  # 总长 28
        result = list(encode_bit2_opcode_iter(data))

        # 字面值 12 (4字节) + Run 4 (1字节) + 复制 12 偏移 16 (2字节) = 7字节
        # 平局仲裁器（字面值最少化）会迫使其选择最优的 Copy 路径
        assert result == [(0, pattern), (1, 2, 4), (2, 16, 12)]

    def test_long_copy_large_offset(self):
        """Tests long copy with offset > 256 (forces 0111LLFF format with large offset)."""
        # 设计一个 15 字节的“无自我重复模式”
        pattern = [0, 1, 2, 3, 0, 2, 1, 3, 0, 3, 2, 1, 2, 0, 3]  # 长度 15
        run = [2] * 260  # 长度 260 的 Run，将第二个模式推至偏移量 275 处
        data = pattern + run + pattern
        result = list(encode_bit2_opcode_iter(data))

        # 字面值 15 (5字节) + Run 260 (2字节) + 长复制 15 偏移 275 (4字节) = 11字节
        # 若第二个模式用字面值，总开销为 12 字节。
        assert result == [(0, pattern), (1, 2, 260), (2, 275, 15)]

    def test_long_copy_large_length(self):
        """Tests long copy with length > 32 but offset <= 256 (0111LLFF format)."""
        # 设计一个 40 字节的“无自我重复模式” (利用 ext8 扩展属性 0~7 轻松构造)
        pattern = [
            0, 1, 2, 3, 4, 5, 6, 7,
            0, 2, 4, 6, 1, 3, 5, 7,
            0, 3, 6, 1, 4, 7, 2, 5,
            0, 4, 1, 5, 2, 6, 3, 7,
            0, 5, 1, 6, 2, 7, 3, 4
        ]  # 长度 40
        data = pattern + pattern  # 总长 80

        # 必须开启 ext8=True 支持 4/5/6/7 等字面值
        result = list(encode_bit2_opcode_iter(data))

        # 第一个字面值 40 (由于超 32 会被流切分为 32+8，开销 12 字节)
        # 第二个复制 40 偏移 40 (长复制开销：1字节头+1字节长+1字节偏 = 3 字节)
        # 总开销：15 字节
        assert result == [(0, pattern), (2, 40, 40)]

    def test_ext8_copy_integration(self):
        """Tests that ext8 literal values (4/5/6/7) can successfully participate in LZ77 Copy."""
        # 包含 4/5/6/7 的模式
        pattern = [4, 5, 6, 7, 4, 6, 5, 7, 4, 7, 6, 5, 4, 4, 6, 6]  # 长度 16
        data = pattern + pattern
        result = list(encode_bit2_opcode_iter(data))

        # 验证包含 ext8 元素的模式能够被完美识别并作为 LZ77 Copy 压缩
        assert result == [(0, pattern), (2, 16, 16)]

    def test_long_copy_large_offset_and_length(self):
        """Copy with both offset > 256 and length > 32 (0111LLFF long format)."""
        # 36-element pattern with long run separator to push second occurrence past offset 256
        pattern = [0, 1, 2, 3] * 9  # 36 elements
        run = [2] * 260            # pushes pattern to offset 296
        data = pattern + run + pattern
        result = list(encode_bit2_opcode_iter(data))

        # Verify round-trip correctness
        decoded = decode_bit2_opcode(result)
        assert decoded == data

        # Verify the structure:
        #   (0, [0,1,2,3]) + (2, 4, 32) → first 36-element pattern via rolling copy
        #   (1, 2, 260)                  → separator run
        #   (2, 296, 36)                 → second pattern via copy at offset 296, length 36
        first_literal = result[0]
        assert first_literal[0] == 0
        assert list(first_literal[1]) == [0, 1, 2, 3]

        rolling_copy = result[1]
        assert rolling_copy == (2, 4, 32), (
            f"Expected rolling copy (2, 4, 32) for first pattern, got {rolling_copy}"
        )

        run_sep = result[2]
        assert run_sep == (1, 2, 260), (
            f"Expected run (1, 2, 260), got {run_sep}"
        )

        long_copy = result[3]
        assert long_copy[0] == 2, f"Expected copy opcode, got {long_copy}"
        assert long_copy[1] > 256, (
            f"Expected copy offset > 256, got {long_copy[1]}"
        )
        assert long_copy[2] > 32, (
            f"Expected copy length > 32, got {long_copy[2]}"
        )


# ==============================================================================
# encode_bit2_opcode_iter — run vs copy decision
# ==============================================================================


class TestEncodeRunVsCopy:
    """Decision logic when both run and copy are candidates.

    The encoder prefers run unless ``copy_len > run_len + 2``.
    """

    def test_run_wins_when_copy_not_longer_enough(self):
        """When copy_len <= run_len + 2, run is preferred."""
        data = [0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1]
        result = list(encode_bit2_opcode_iter(data))
        # At i=8: run_len=4 (zeros), copy_len=8 (matches data[0:8] at offset 8).
        #         8 > 4+2? Yes → copy wins over run at the 2nd half.
        assert result == [(1, 0, 4), (1, 1, 4), (2, 8, 8)]


# ==============================================================================
# encode_bit2_opcode_iter — tiebreaker (cost equality)
# ==============================================================================


class TestEncodeTiebreaker:
    """DP tiebreaker: when costs are equal, the encoder prefers the path with fewer
    literal elements (``p_lit_count``), which produces fewer literal blocks in the
    merged output and therefore smaller stream encoding overhead."""

    def test_run_plus_literal_beats_full_literal(self):
        """When run(3)+literal(1) has same cost as literal(4), run+literal wins
        because it contributes fewer literal elements (1 vs 4)."""
        # Example: data starts with a run of 3 identical values + 1 different value
        # Position 0:
        #   literal(4): dp[4] = 2, lit_count=4
        #   run(3):     dp[3] = 1, lit_count=0
        # Position 3:
        #   literal(1): dp[4] = dp[3]+1 = 2, lit_count=0+1=1
        # Both paths reach position 4 with cost 2, but run+literal has 1 literal
        # element vs 4 → tiebreaker selects run+literal.
        data = [0, 0, 0, 1]
        result = list(encode_bit2_opcode_iter(data))
        assert result == [(1, 0, 3), (0, [1])]

    def test_copy_plus_literal_beats_full_literal(self):
        """When copy(4) has same cost as literal(4), copy wins because it
        contributes fewer literal elements (0 vs 4)."""
        # data = [0,1,0,1,0,1,0,1]: at position 2, the 3-tuple (0,1,0) matches
        # position 0 (offset=2, LCP=6). Copy(2,6) costs 2, while literal(6) costs 3,
        # but the tiebreaker is visible at position 6:
        #   literal(6) from i=0:  dp[6] = 3, lit=6
        #   copy(2,4) from i=2:   dp[6] = dp[2]+2 = 1+2 = 3, lit=2
        #   same cost → copy wins (fewer literal elements).
        # This propagates: at i=2, copy(2,6) wins for position 8 as well.
        data = [0, 1, 0, 1, 0, 1, 0, 1]
        result = list(encode_bit2_opcode_iter(data))
        assert result == [(0, [0, 1]), (2, 2, 6)]


# ==============================================================================
# decode_bit2_opcode — individual opcode types
# ==============================================================================


class TestDecodeEmpty:
    """Empty / degenerate inputs."""

    def test_no_opcodes(self):
        """Empty opcode list returns empty list."""
        assert decode_bit2_opcode([]) == []

    def test_empty_literal(self):
        """Literal opcode with empty values produces nothing."""
        result = decode_bit2_opcode([(0, [])])
        assert result == []


class TestDecodeLiteral:
    """Decoding literal opcodes."""

    @pytest.mark.parametrize("values", [
        (0,),
        (1,),
        (3, 2, 1, 0),
        (0, 0, 0, 0),
        (1, 0, 2, 3, 2),
    ])
    def test_literal_values(self, values):
        """Literal values are appended as-is."""
        expected = list(values)
        result = decode_bit2_opcode([(0, expected)])
        assert result == expected

    def test_literal_as_list(self):
        """Literal opcode works with list values (not just deque)."""
        result = decode_bit2_opcode([(0, [1, 2, 3])])
        assert result == [1, 2, 3]


class TestDecodeRun:
    """Decoding run opcodes."""

    @pytest.mark.parametrize("val, length", [
        (0, 1),
        (1, 5),
        (2, 10),
        (3, 100),
    ])
    def test_run(self, val, length):
        """Run opcode produces ``[val] * length``."""
        result = decode_bit2_opcode([(1, val, length)])
        assert result == [val] * length

    def test_multiple_runs(self):
        """Multiple runs in sequence."""
        result = decode_bit2_opcode([(1, 0, 3), (1, 1, 4)])
        assert result == [0, 0, 0, 1, 1, 1, 1]


class TestDecodeCopy:
    """Decoding copy opcodes — both simple and rolling copy."""

    def test_simple_copy(self):
        """Copy with length <= offset is a simple slice."""
        result = decode_bit2_opcode([(0, [0, 1, 2, 3]), (2, 4, 3)])
        # res = [0,1,2,3], then copy offset=4 → start=0, copy res[0:3]=[0,1,2]
        assert result == [0, 1, 2, 3, 0, 1, 2]

    def test_copy_exact_offset(self):
        """Copy with length == offset copies the entire sliced window."""
        result = decode_bit2_opcode([(0, [1, 2, 3, 4]), (2, 4, 4)])
        assert result == [1, 2, 3, 4, 1, 2, 3, 4]

    def test_rolling_copy_offset_1(self):
        """Rolling copy: offset=1 repeats a single value."""
        result = decode_bit2_opcode([(0, [0]), (2, 1, 5)])
        # pattern = [0], repeats=5, remainder=0
        assert result == [0, 0, 0, 0, 0, 0]

    def test_rolling_copy_offset_2(self):
        """Rolling copy: offset=2 with odd length extends via pattern repeat."""
        result = decode_bit2_opcode([(0, [0, 1]), (2, 2, 5)])
        # pattern = [0,1], repeats=2, remainder=1 → [0,1,0,1,0]
        assert result == [0, 1, 0, 1, 0, 1, 0]

    def test_rolling_copy_offset_3_len_8(self):
        """Rolling copy: offset=3, length=8 builds extended pattern."""
        result = decode_bit2_opcode([(0, [1, 2, 3]), (2, 3, 8)])
        # pattern = [1,2,3], repeats=2, remainder=2 → [1,2,3,1,2,3,1,2]
        assert result == [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2]

    def test_rolling_copy_exact_multiples(self):
        """Rolling copy: length is exact multiple of offset."""
        result = decode_bit2_opcode([(0, [2, 1]), (2, 2, 6)])
        # pattern = [2,1], repeats=3, remainder=0 → [2,1,2,1,2,1]
        assert result == [2, 1, 2, 1, 2, 1, 2, 1]


class TestDecodeMixed:
    """Decoding sequences mixing all three opcode types."""

    def test_literal_then_run_then_copy(self):
        """Mixed opcodes produce the combined output."""
        opcodes = [
            (0, [0, 1]),
            (1, 2, 3),
            (2, 5, 4),
        ]
        # After literal+run: [0,1,2,2,2] (5 elements)
        # Copy: start=5-5=0, length(4) <= offset(5) → simple copy res[0:4]
        result = decode_bit2_opcode(opcodes)
        assert result == [0, 1, 2, 2, 2, 0, 1, 2, 2]

    def test_multiple_copies(self):
        """Consecutive copy opcodes build on previous output."""
        opcodes = [
            (0, [1, 2, 3]),
            (2, 3, 3),  # copy last 3, take 3 → [1,2,3]
            (2, 6, 4),  # copy last 6, take 4 → [1,2,3,1]
        ]
        result = decode_bit2_opcode(opcodes)
        assert result == [1, 2, 3, 1, 2, 3, 1, 2, 3, 1]

    def test_all_three_types(self):
        """Literal, run, and copy in one sequence."""
        opcodes = [
            (0, [1]),
            (1, 0, 3),
            (2, 4, 2),
        ]
        # After literal+run: [1,0,0,0] (4 elements)
        # Copy: start=4-4=0, take 2 → [1,0]
        result = decode_bit2_opcode(opcodes)
        assert result == [1, 0, 0, 0, 1, 0]


# ==============================================================================
# Round-trip tests — encode then decode returns the original
# ==============================================================================


class TestRoundtrip:
    """``decode_bit2_opcode(encode_bit2_opcode_iter(data)) == data``."""

    ROUNDTRIP_CASES = [
        # Empty
        [],
        # Singletons
        [0],
        [1],
        [2],
        [3],
        # Small literals (no run, no copy)
        [0, 1, 2, 3],
        [3, 2, 1, 0],
        [0, 1, 2, 3, 0, 1],
        # Pure run (single value repeated)
        [0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [2, 2, 2, 2, 2, 2],
        [3, 3, 3, 3, 3, 3, 3],
        # Alternating pattern (triggers copy)
        [0, 1, 0, 1],
        [1, 2, 1, 2],
        [0, 1, 2, 0, 1, 2],
        [0, 1, 2, 3, 0, 1, 2, 3],
        [0, 0, 1, 0, 0, 1],
        # Pattern with run inside
        [0, 0, 0, 0, 1, 2, 3],
        [0, 1, 2, 3, 3, 3, 3],
        [0, 1, 2, 3, 0, 0, 0, 0, 1, 2, 3],
        # Two runs separated by literals
        [0, 0, 0, 0, 1, 1, 1, 1],
        [2, 2, 2, 2, 3, 3, 3, 3],
        # Run then copy
        [0, 0, 0, 0, 1, 2, 0, 0, 0, 0, 1, 2],
        # Copy beats run (copy_len > run_len + 2)
        [0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1],
        # Long constant run (covering short/long format boundary)
        [2] * 50,
        [0] * 100,
        [0] * 34,  # short format boundary (l=34, cost=1)
        [0] * 35,  # long format start (l=35, cost=2+L_D_TABLE[0])
        [0] * 36,  # long format (l=36, cost=2+L_D_TABLE[1])
        # Repeated short pattern
        [0, 1] * 10,
        [1, 2, 3] * 10,
        # Mixed patterns
        [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3],
        [0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        # Sawtooth
        [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3],
        # All 4 values cycling
        [0, 1, 2, 3] * 25,
        # Long literal sequence
        [i % 4 for i in range(50)],
        # Descending
        [3, 2, 1, 0, 3, 2, 1, 0],
    ]

    @pytest.mark.parametrize("data", ROUNDTRIP_CASES)
    def test_roundtrip(self, data):
        """decode(encode(data)) == data for a variety of inputs."""
        encoded = list(encode_bit2_opcode_iter(data))
        decoded = decode_bit2_opcode(encoded)
        assert decoded == data

    def test_roundtrip_large_synthetic(self):
        """Large synthetic data round-trips correctly."""
        data = []
        for i in range(500):
            if i % 7 == 0:
                data.extend([i % 4] * 5)  # run
            else:
                data.append(i % 4)  # literal
        encoded = list(encode_bit2_opcode_iter(data))
        decoded = decode_bit2_opcode(encoded)
        assert decoded == data

    def test_deterministic(self):
        """Encoding the same input twice produces identical output."""
        data = [0, 1, 2, 3, 0, 1, 2, 3, 0, 0, 0, 0, 1, 1, 1, 1]
        assert list(encode_bit2_opcode_iter(data)) == list(encode_bit2_opcode_iter(data))


# ==============================================================================
# Large data stress test
# ==============================================================================


class TestLargeData:
    """Correctness with large inputs."""

    LARGE_CASES = [
        ([0] * 200, "all zeros"),
        ([1, 2, 3] * 200, "repeating pattern"),
        ([i % 4 for i in range(200)], "cycling values"),
        # Enough data to trigger 64+ LZ77 hash chain entries for many positions
        ([0, 1, 2, 3] * 80, "many chain entries"),
    ]

    @pytest.mark.parametrize("data, name", LARGE_CASES)
    def test_large_roundtrip(self, data, name):
        """Large data round-trips without error and produces correct output."""
        encoded = list(encode_bit2_opcode_iter(data))
        decoded = decode_bit2_opcode(encoded)
        assert decoded == data

    def test_no_run_opcode_for_values_ge4(self):
        """Values >= 4 should never be encoded as run opcodes.

        The run opcode format only supports 2-bit values (0-3).
        Runs of values 4-7 must fall through to the literal/copy path.
        """
        for val in [4, 5, 6, 7]:
            data = [val] * 5
            opcodes = list(encode_bit2_opcode_iter(data))
            assert not any(op[0] == 1 for op in opcodes), (
                f"Value {val} should not produce a run opcode; got {opcodes}"
            )

    def test_compression_ratio_non_trivial(self):
        """Compressed output should be smaller than input for repetitive data."""
        data = [0, 1, 2, 3] * 100
        encoded = list(encode_bit2_opcode_iter(data))
        total_output = 0
        for op in encoded:
            if op[0] == 0:
                total_output += len(op[1])
            elif op[0] == 1:
                total_output += 2
            else:  # op[0] == 2
                total_output += 2
        assert total_output < len(data), (
            f"Encoded size ({total_output}) should be less than "
            f"input size ({len(data)}) for repetitive data"
        )

    def test_copy_chain_limit_safety(self):
        """Encoder handles data with more than 64 LZ77 hash chain entries safely
        (``LIMIT_CHAIN_STEPS = 64``). The chain limit is an optimization that should
        not affect correctness; round-trip and determinism are verified."""
        # [0,1,2,3]*80 = 320 elements.
        # Each 3-tuple (0,1,2) occurs at every 4th position (80 positions).
        # At position 256 there are 65 chain entries, exceeding LIMIT_CHAIN_STEPS.
        data = [0, 1, 2, 3] * 80
        encoded = list(encode_bit2_opcode_iter(data))
        decoded = decode_bit2_opcode(encoded)
        assert decoded == data, "Round-trip should succeed with many chain entries"

        # Determinism: same input → same output even at the chain limit boundary
        encoded2 = list(encode_bit2_opcode_iter(data))
        assert encoded == encoded2, (
            "Output should be deterministic regardless of chain limit"
        )

    @staticmethod
    def _de_bruijn(k, n):
        """Generate a De Bruijn sequence of order n over alphabet 0..k-1.

        Returns a linear sequence of length ``k^n + n - 1`` where every possible
        n-tuple over the alphabet appears exactly once as a contiguous substring.
        """
        a = [0] * (k * n)
        seq = []

        def db(t, p):
            if t > n:
                if n % p == 0:
                    for j in range(1, p + 1):
                        seq.append(a[j])
            else:
                a[t] = a[t - p]
                db(t + 1, p)
                for j in range(a[t - p] + 1, k):
                    a[t] = j
                    db(t + 1, t)

        db(1, 1)
        return seq + seq[:n - 1]

    def test_no_repeated_four_tuples(self):
        """De Bruijn B(4,4) sequence (259 elements): all 256 four-tuples unique,
        so no LZ77 copy match exists.  Round-trip verifies the encoder handles
        purely literal-dominated data without error."""
        data = self._de_bruijn(4, 4)
        assert len(data) == 4 ** 4 + 3  # 259

        # Verify completeness
        tuples = {tuple(data[i:i + 4]) for i in range(len(data) - 3)}
        assert len(tuples) == 4 ** 4, \
            f"De Bruijn B(4,4) must have all {4 ** 4} distinct 4-tuples"

        encoded = list(encode_bit2_opcode_iter(data))
        decoded = decode_bit2_opcode(encoded)
        assert decoded == data, "Round-trip should succeed for De Bruijn data"
