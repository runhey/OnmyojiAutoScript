from collections import deque
from itertools import batched

from oas.ext.algorithm.const import MAX_UINT8, MAX_UINT16, MAX_UINT24, MAX_UINT32
from oas.ext.algorithm.unpack import unpack_little_int
from oas.ext.algorithm.vint import decode_vint, encode_vint


def encode_bit2_opcode_iter(data):
    """
    将输入的 2-bit 数据流转换为操作元组列表

    Args:
        data (list[int] | deque[int]): value must be 0, 1, 2, 3

    Yields:
        tuple: operation code
            - (0, list[int]): literal values
            - (1, int, int): run value and length
            - (2, int, int): copy offset and length
    """
    mv = memoryview(bytes(data))
    n = len(mv)
    if n == 0:
        return

    INF = MAX_UINT32

    # ==========================================
    # 1. 预计算 Run 长度 (逆向扫描, 时间 O(N))
    # ==========================================
    run_lens = [0] * n
    if n > 0:
        run_lens[n - 1] = 1
        for i in range(n - 2, -1, -1):
            if mv[i] == mv[i + 1]:
                run_lens[i] = run_lens[i + 1] + 1
            else:
                run_lens[i] = 1

    # ==========================================
    # 2. 预计算 LZ77 哈希链 (前向扫描, 时间 O(N))
    # ==========================================
    prev_chain = [-1] * n
    head = {}  # 键为 (a, b, c) 元组，值为最新的索引

    for i in range(n - 2):
        key = (mv[i], mv[i + 1], mv[i + 2])
        prev_chain[i] = head.get(key, -1)
        head[key] = i
    # ==========================================
    # 3. 预计算两大开销静态查找表
    # ==========================================
    # 变长小端整数对应的 d 字节开销表
    L_D_TABLE = [0] * (n + 2)
    for val in range(n + 2):
        if val <= MAX_UINT8:
            l_d = 0
        elif val <= MAX_UINT16:
            l_d = 1
        elif val <= MAX_UINT24:
            l_d = 2
        else:
            l_d = 3
        L_D_TABLE[val] = l_d

    # Run 开销表
    RUN_COST_TABLE = [INF] * (n + 1)
    for l in range(3, n + 1):
        if l < 35:
            RUN_COST_TABLE[l] = 1
        else:
            RUN_COST_TABLE[l] = 2 + L_D_TABLE[l - 35]

    # ==========================================
    # 4. DP 最优解转移
    # ==========================================
    LITERAL_COSTS = (
        0, 1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5,
        6, 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 9,
        10, 10
    )
    LIT_TRANSITIONS = tuple(range(35))

    dp = [INF] * (n + 1)
    dp[0] = 0

    p_prev = [0] * (n + 1)
    p_op = [0] * (n + 1)
    p_offset = [0] * (n + 1)

    # 第二优化目标：记录到达各站点的字面值元素累计总数
    p_lit_count = [INF] * (n + 1)
    p_lit_count[0] = 0

    # 追溯链深度 64。后续链条目由 chain-skip 跳过 (LCP <= best 时
    # 仅做 O(1) 偏移比较)，64 限制了第一链条目的 LCP 计算开销。
    LIMIT_CHAIN_STEPS = 64

    for i in range(n):
        current_dp = dp[i]
        if current_dp == INF:
            continue

        current_lit_count = p_lit_count[i]

        # --- A. 字面值转移 ---
        rem = n - i
        for k in LIT_TRANSITIONS:
            if k > rem:
                if rem > 0:
                    cost = current_dp + LITERAL_COSTS[rem]
                    new_lit = current_lit_count + rem
                    # 开销更小，或者开销相同但字面值数更少时更新
                    if cost < dp[n] or (cost == dp[n] and new_lit < p_lit_count[n]):
                        dp[n] = cost
                        p_lit_count[n] = new_lit
                        p_prev[n], p_op[n] = i, 0
                break
            cost = current_dp + LITERAL_COSTS[k]
            next_idx = i + k
            new_lit = current_lit_count + k
            if cost < dp[next_idx] or (cost == dp[next_idx] and new_lit < p_lit_count[next_idx]):
                dp[next_idx] = cost
                p_lit_count[next_idx] = new_lit
                p_prev[next_idx], p_op[next_idx] = i, 0

        # --- B. Run 转移 (32 窗口剪枝 + 开销均匀跳过) ---
        r_len = run_lens[i]
        if r_len >= 3 and mv[i] <= 3:
            start_l = r_len - 32
            if start_l < 3:
                start_l = 3

            # Run 开销在窗口内最多两种 (短格式 cost=1, 长格式 cost=2+L_D_TABLE)。
            # 若窗口内开销均匀，取最大长度即可 (相同开销，走得更远)。
            # 若窗口跨越开销边界，安全回退到遍历所有长度。
            if RUN_COST_TABLE[start_l] == RUN_COST_TABLE[r_len]:
                # Run 开销均匀: 仅检查窗口内最大长度
                l = r_len
                cost = current_dp + RUN_COST_TABLE[l]
                next_idx = i + l
                if cost < dp[next_idx] or (cost == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                    dp[next_idx] = cost
                    p_lit_count[next_idx] = current_lit_count
                    p_prev[next_idx], p_op[next_idx] = i, 1
            else:
                # 窗口跨越短/长格式或 L_D_TABLE 分界: 遍历所有长度
                for l in range(start_l, r_len + 1):
                    cost = current_dp + RUN_COST_TABLE[l]
                    next_idx = i + l
                    if cost < dp[next_idx] or (cost == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                        dp[next_idx] = cost
                        p_lit_count[next_idx] = current_lit_count
                        p_prev[next_idx], p_op[next_idx] = i, 1

        # --- C. 无损状态空间的高速 LZ77 转移 ---
        if i < n - 2:
            idx = prev_chain[i]
            step_chain = 0
            # Track best LCP seen per offset category. The first chain entry
            # (closest match) always has the smallest offset and cheapest copy
            # cost; later entries with same or worse cost and <= LCP cannot
            # improve any dp position, so we skip them entirely.
            best_l_short = 0  # offset <= 256  (cost 2/3 + L_D_TABLE)
            best_l_long = 0   # offset > 256   (cost 3+fd + L_D_TABLE)
            while idx != -1 and step_chain < LIMIT_CHAIN_STEPS:
                # 极速 C 级切片比较 + 指数增长 + 二分收窄求 LCP
                max_len = n - i
                low_l = 3
                step_growth = 1

                while True:
                    test_len = low_l + step_growth
                    if test_len > max_len:
                        test_len = max_len

                    if mv[idx: idx + test_len] == mv[i: i + test_len]:
                        low_l = test_len
                        if test_len == max_len:
                            break
                        step_growth *= 2
                    else:
                        break

                high_l = low_l + step_growth - 1
                if high_l > max_len:
                    high_l = max_len

                l = low_l
                binary_low = low_l + 1
                while binary_low <= high_l:
                    mid = (binary_low + high_l) // 2
                    if mv[idx: idx + mid] == mv[i: i + mid]:
                        l = mid
                        binary_low = mid + 1
                    else:
                        high_l = mid - 1

                c_offset = i - idx

                # Skip this entry if a previous entry already covered this
                # range with the same or better cost.
                if c_offset <= 256:
                    if l <= best_l_short:
                        idx = prev_chain[idx]
                        step_chain += 1
                        continue
                    best_l_short = l
                else:
                    if l <= best_l_long:
                        idx = prev_chain[idx]
                        step_chain += 1
                        continue
                    best_l_long = l

                f_d = L_D_TABLE[c_offset - 1]

                if c_offset <= 256:
                    # Band A: [3, min(l, 32)], cost = current_dp + 2 (short copy format)
                    # Pre-check: dp is non-decreasing; if the END of the band
                    # cannot be improved, no position in the band can.
                    limit32 = l if l < 33 else 32
                    if limit32 >= 3:
                        ca = current_dp + 2
                        end32 = i + limit32
                        if ca < dp[end32] or (ca == dp[end32] and current_lit_count < p_lit_count[end32]):
                            for curr_l in range(3, limit32 + 1):
                                next_idx = i + curr_l
                                if ca < dp[next_idx] or (ca == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                                    dp[next_idx] = ca
                                    p_lit_count[next_idx] = current_lit_count
                                    p_prev[next_idx] = i
                                    p_op[next_idx] = 2
                                    p_offset[next_idx] = c_offset
                    # Band B: [33, min(l, 256)], cost = current_dp + 3 (long format, L=0)
                    if l > 32:
                        limit256 = l if l < 257 else 256
                        cb = current_dp + 3
                        end256 = i + limit256
                        if cb < dp[end256] or (cb == dp[end256] and current_lit_count < p_lit_count[end256]):
                            for curr_l in range(33, limit256 + 1):
                                next_idx = i + curr_l
                                if cb < dp[next_idx] or (cb == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                                    dp[next_idx] = cb
                                    p_lit_count[next_idx] = current_lit_count
                                    p_prev[next_idx] = i
                                    p_op[next_idx] = 2
                                    p_offset[next_idx] = c_offset
                    # Band C: [257, l], cost varies with L_D_TABLE
                    # Variable-cost band: check at START (lowest cost). If start
                    # cannot be improved, later positions (with higher cost) cannot.
                    if l > 256:
                        start_cost = current_dp + 3 + L_D_TABLE[256]
                        start_idx = i + 257
                        if start_cost < dp[start_idx] or (start_cost == dp[start_idx] and current_lit_count < p_lit_count[start_idx]):
                            for curr_l in range(257, l + 1):
                                next_idx = i + curr_l
                                cost = current_dp + 3 + L_D_TABLE[curr_l - 1]
                                if cost < dp[next_idx] or (cost == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                                    dp[next_idx] = cost
                                    p_lit_count[next_idx] = current_lit_count
                                    p_prev[next_idx] = i
                                    p_op[next_idx] = 2
                                    p_offset[next_idx] = c_offset
                else:
                    base_cost = 3 + f_d
                    # Band A: [3, min(l, 256)], cost = current_dp + base_cost (constant)
                    limit256 = l if l < 257 else 256
                    if limit256 >= 3:
                        ca = current_dp + base_cost
                        end_l256 = i + limit256
                        if ca < dp[end_l256] or (ca == dp[end_l256] and current_lit_count < p_lit_count[end_l256]):
                            for curr_l in range(3, limit256 + 1):
                                next_idx = i + curr_l
                                if ca < dp[next_idx] or (ca == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                                    dp[next_idx] = ca
                                    p_lit_count[next_idx] = current_lit_count
                                    p_prev[next_idx] = i
                                    p_op[next_idx] = 2
                                    p_offset[next_idx] = c_offset
                    # Band B: [257, l], cost varies with L_D_TABLE
                    # Variable-cost band: check at START for the same reason.
                    if l > 256:
                        start_cost = current_dp + base_cost + L_D_TABLE[256]
                        start_idx = i + 257
                        if start_cost < dp[start_idx] or (start_cost == dp[start_idx] and current_lit_count < p_lit_count[start_idx]):
                            for curr_l in range(257, l + 1):
                                next_idx = i + curr_l
                                cost = current_dp + base_cost + L_D_TABLE[curr_l - 1]
                                if cost < dp[next_idx] or (cost == dp[next_idx] and current_lit_count < p_lit_count[next_idx]):
                                    dp[next_idx] = cost
                                    p_lit_count[next_idx] = current_lit_count
                                    p_prev[next_idx] = i
                                    p_op[next_idx] = 2
                                    p_offset[next_idx] = c_offset

                idx = prev_chain[idx]
                step_chain += 1

    # ==========================================
    # 5. 逆向重构与合并 (单遍扫描)
    # ==========================================
    merged = deque()
    literal_slices = []  # list of memoryview slices in reverse order
    curr = n
    while curr > 0:
        prev = p_prev[curr]
        op_type = p_op[curr]

        if op_type == 0:
            literal_slices.append(mv[prev:curr])
        else:
            if literal_slices:
                # Flatten slices in forward order
                flat = []
                for sl in reversed(literal_slices):
                    flat.extend(sl)
                literal_slices = []
                merged.appendleft((0, flat))
            if op_type == 1:
                merged.appendleft((1, mv[prev], curr - prev))
            else:
                merged.appendleft((2, p_offset[curr], curr - prev))
        curr = prev

    if literal_slices:
        flat = []
        for sl in reversed(literal_slices):
            flat.extend(sl)
        merged.appendleft((0, flat))

    yield from merged


def decode_bit2_opcode(opcodes):
    """
    将操作元组列表重新解码为原始的 list[int]

    Args:
        opcodes (Iterable[tuple])

    Returns:
        list[int]: list of 2 bits value, value must be 0, 1, 2, 3
    """
    res = []

    for opcode in opcodes:
        op_type = opcode[0]

        if op_type == 0:
            # 0: literal values (list[int])
            res.extend(opcode[1])

        elif op_type == 1:
            # 1: run value and length
            _, run_val, run_len = opcode
            res.extend([run_val] * run_len)

        elif op_type == 2:
            # 2: copy offset and length
            _, offset, length = opcode
            start = len(res) - offset

            if length <= offset:
                # 普通复制，直接切片
                res.extend(res[start: start + length])
            else:
                # 滚动复制 (Rolling Copy)，例如 offset=1, length=5
                # 利用切片乘法避免 Python 层的 for 循环
                pattern = res[start: start + offset]
                repeats = length // offset
                remainder = length % offset
                res.extend(pattern * repeats + pattern[:remainder])

    return res


def encode_length_int(length):
    """
    Encode length to bytes

    Args:
        length (int): length to encode

    Returns:
        tuple: (d, *length_bytes)
            D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
    """
    if length <= MAX_UINT8:
        d = 0
        return d, length
    elif length <= MAX_UINT16:
        d = 1
        return d, length % 256, length // 256
    elif length <= MAX_UINT24:
        d = 2
        first = length // 256
        return d, length % 256, first % 256, first // 256
    elif length <= MAX_UINT32:
        d = 3
        first = length // 256
        second = first // 256
        return d, length % 256, first % 256, second % 256, second // 256
    else:
        raise ValueError(f"[encode_bit2] Length is too large: {length}")


def _encode_literal_iter(items):
    """
    Encode a list of 2bits to bytes in literal

    Args:
        items (Iterable[int]): list of 2bits value, value must be 0, 1, 2, 3

    Yields:
        int: compressed data in uint8
    """
    for item_batch in batched(items, 34):
        n = len(item_batch)
        # Use compact formats for small trailing batches
        # 000000XX: 1 item
        if n == 1:
            yield item_batch[0]
            continue
        # 0001XXYY: 2 item
        if n == 2:
            yield 16 + item_batch[0] * 4 + item_batch[1]
            continue
        # 001NNNNN: pack N+3 items, N (0~31), 1 header byte + ceil(N/4) data bytes
        yield 29 + n
        stack_count = 0
        stack_val = 0
        for item in item_batch:
            stack_val = stack_val * 4 + item
            stack_count += 1
            # each following bytes are AABBCCDD
            if stack_count == 4:
                yield stack_val
                stack_val = 0
                stack_count = 0
        # trailing 00 to fill up to a full byte, e.g. AABB0000
        if stack_count > 0:
            trailing = (4 - stack_count) * 2
            trailing = 2 ** trailing
            yield stack_val * trailing


def encode_bit2_stream_iter(opcodes, ext8=False):
    """
    Compress operations to store a list of 2bits
    1. literal operations, op=(0, data), e.g. (0, [1, 2, 3, 4, ...])
    000000XX: 1 item
    0001XXYY: 2 item
    001NNNNN: pack N+3 items, N (0~31), indicates to read 1~9 bytes, each following bytes are AABBCCDD
              last byte may have trailing 00 to fill up to a full byte, e.g. AABB0000
    (NOT PLANNED) 000001DD: pack N+16 items, N (0~2^32),
              D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
    000001XX: 1 item, item is 4/5/6/7
              This is available when ext8 is enabled
    2. run operations, op=(1, item, run), e.g. (1, 2, 35)
    1XXNNNNN: run XX for N+3 times, N (0~31)
    0110XXDD: run XX for N+35 times, N (0~2^32),
              D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
    3. copy operations, op=(2, offset, length), e.g. (2, 28, 5)
    010LLLLL: Copy from offset=F+1 length=L+1
              L (0~31),
              this indicates to read next byte as F (0~255)
    0111LLFF: Copy from offset=F+1 length=L+1
              L (0~3) indicates to read L+1 bytes of L (0~2^32), L is packed in little-endian
              F (0~3) indicates to read F+1 bytes of F (0~2^32), F is packed in little-endian

    Args:
        opcodes (Iterable[tuple]):
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Yields:
        int: compressed data in uint8
    """
    for opcode in opcodes:
        op_type = opcode[0]

        # 0: literal values (list[int])
        if op_type == 0:
            items = opcode[1]
            if ext8:
                int4 = []
                for item in items:
                    if item <= 3:
                        int4.append(item)
                    else:
                        # flush int4
                        if int4:
                            yield from _encode_literal_iter(int4)
                            int4 = []
                        # 000001XX: 1 item, item is 4/5/6/7
                        yield item
                # flush int4
                if int4:
                    yield from _encode_literal_iter(int4)
            else:
                yield from _encode_literal_iter(items)

        # 1: run value and length
        elif op_type == 1:
            item = opcode[1]
            run = opcode[2]
            # 1XXNNNNN: run XX for N+3 times, N (0~31)
            if run < 35:
                yield 128 + item * 32 + (run - 3)
                continue
            # 0110XXDD: run XX for N+35 times, N (0~2^32),
            #           D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
            d, *length_bytes = encode_length_int(run - 35)
            yield 96 + item * 4 + d
            yield from length_bytes

        # 2: copy offset and length
        elif op_type == 2:
            offset = opcode[1]
            length = opcode[2]
            # 010LLLLL: Copy from offset=F+1 length=L+1
            #           L (0~31),
            #           this indicates to read next byte as F (0~255)
            if length <= 32 and offset <= 256:
                yield 63 + length
                yield offset - 1
                continue
            # 0111LLFF: Copy from offset=F+1 length=L+1
            #           L (0~3) indicates to read L+1 bytes of L (0~2^32), L is packed in little-endian
            #           F (0~3) indicates to read F+1 bytes of F (0~2^32), F is packed in little-endian
            l_d, *l_bytes = encode_length_int(length - 1)
            f_d, *f_bytes = encode_length_int(offset - 1)
            yield 112 + l_d * 4 + f_d
            yield from l_bytes
            yield from f_bytes

        # this shouldn't happen
        else:
            raise ValueError(f"[encode_bit2] Invalid opcode: {opcode}")


def decode_bit2_stream_iter(data, total, ext8=False):
    """
    Decode compressed operations to opcodes list
    See encode_bit2_stream_iter for more information

    Args:
        data (memoryview): compressed data
        total (int): Total numbers
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Returns:
        tuple[list[int], int]: (list of opcodes, read bytes count)

    Raises:
        ValueError: If the stream ends before ``total`` numbers are
            decoded, or an opcode is invalid
    """
    count = 0
    read = 0
    opcodes = []
    if total == 0:
        return opcodes, read
    while True:
        try:
            byte = data[read]
        except IndexError:
            raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
        read += 1
        # 1XXNNNNN: run XX for N+3 times, N (0~31)
        if byte >= 128:
            item = (byte // 32) % 4
            run = (byte % 32) + 3
            opcodes.append((1, item, run))
            count += run
        # 0111LLFF: copy offset and length
        #           L (0~3) indicates to read L+1 bytes, F (0~3) indicates to read F+1 bytes
        elif byte >= 112:
            l_d = (byte % 16) // 4
            f_d = byte % 4
            length = unpack_little_int(data, read, l_d + 1) + 1
            read += l_d + 1
            offset = unpack_little_int(data, read, f_d + 1) + 1
            read += f_d + 1
            opcodes.append((2, offset, length))
            count += length
        # 0110XXDD: run XX for N+35 times, N (0~2^32),
        #           D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
        elif byte >= 96:
            item = (byte % 16) // 4
            d = byte % 4 + 1
            length = unpack_little_int(data, read, d) + 35
            opcodes.append((1, item, length))
            count += length
            read += d
        # 010LLLLL: Copy from offset=F+1 length=L+1
        #           L (0~31),
        #           this indicates to read next byte as F (0~255)
        elif byte >= 64:
            length = (byte % 32) + 1
            try:
                offset = data[read] + 1
            except IndexError:
                raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
            read += 1
            opcodes.append((2, offset, length))
            count += length
        # 001NNNNN: pack N+3 items, N (0~31)
        elif byte >= 32:
            n = byte - 29  # 3-34 items
            packed_count = (n + 3) // 4
            # every packed byte carries 4 items, a stream that ends
            # before them is truncated, check once instead of per byte
            if read + packed_count > len(data):
                raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
            remain_n = n
            items = []
            for _ in range(packed_count):
                packed = data[read]
                read += 1
                # each following bytes are AABBCCDD
                if remain_n >= 4:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    item3 = (packed // 4) % 4
                    item4 = packed % 4
                    items.extend([item1, item2, item3, item4])
                    remain_n -= 4
                # trailing 00 to fill up to a full byte, e.g. AABB0000
                elif remain_n == 3:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    item3 = (packed // 4) % 4
                    items.extend([item1, item2, item3])
                    remain_n = 0
                elif remain_n == 2:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    items.extend([item1, item2])
                    remain_n = 0
                elif remain_n == 1:
                    item1 = packed // 64
                    items.append(item1)
                    remain_n = 0
            opcodes.append((0, items))
            count += n
        # 0001XXYY: 2 item
        elif byte >= 16:
            first = (byte % 16) // 4
            second = byte % 4
            opcodes.append((0, [first, second]))
            count += 2
        elif byte >= 4:
            # 000001XX: 1 item, item is 4/5/6/7
            #           This is available when ext8 is enabled
            if ext8 and byte < 8:
                opcodes.append((0, [byte]))
                count += 1
            # invalid: byte>=000000XX
            else:
                raise ValueError(f"[decode_bit2] Invalid opcode: {byte}")
        # 000000XX: 1 item
        elif byte >= 0:
            opcodes.append((0, [byte]))
            count += 1

        # check total
        if count >= total:
            break

    return opcodes, read


def _encode_value_check(data, ext8=False):
    """
    Check if the values are valid for bit2 encoding

    Args:
        data (list[int] | deque[int]): Data to encode
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Raises:
        ValueError: If the values are invalid
    """
    if not data:
        return
    min_val = min(data)
    max_val = max(data)
    if min_val < 0:
        raise ValueError(f"[encode_bit2] Invalid value: {min_val}, value must be >= 0")
    if ext8:
        if max_val > 7:
            raise ValueError(f"[encode_bit2] Invalid value: {max_val}, value must be <= 7 if ext8 is enabled")
    else:
        if max_val > 3:
            raise ValueError(f"[encode_bit2] Invalid value: {max_val}, value must be <= 3 if ext8 is disabled")


def encode_bit2(data, ext8=False):
    """
    Encode data to bit2 format with a vint count prefix (see encode_vint):
    [count]: number of values
    [stream]: bit2 compressed values

    The count prefix makes the encoding self-describing, decode_bit2 does
    not need to know the number of values in advance.

    Args:
        data (list[int] | deque[int]): Data to encode
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Returns:
        bytes: Encoded data
    """
    _encode_value_check(data, ext8)
    opcodes = encode_bit2_opcode_iter(data)
    stream = encode_bit2_stream_iter(opcodes, ext8=ext8)
    return encode_vint(len(data)) + bytes(stream)


def decode_bit2(data, ext8=False):
    """
    Decode bit2 format data to list[int].
    The number of values is read from the vint count prefix, the caller
    does not need to pass it in.

    Args:
        data (memoryview | bytes): Encoded data
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Returns:
        tuple[list[int], int]: (list of values, bytes consumed)

    Raises:
        ValueError: If data is truncated or contains invalid opcodes
    """
    if isinstance(data, bytes):
        data = memoryview(data)
    if not data:
        raise ValueError('[decode_bit2] Data truncated: missing vint count prefix')
    total, read = decode_vint(data)
    opcodes, read_stream = decode_bit2_stream_iter(data[read:], total, ext8=ext8)
    read += read_stream
    values = decode_bit2_opcode(opcodes)
    # decode_bit2_stream_iter stops at count >= total, so a run opcode can
    # cross the total boundary and yield more values than declared. This
    # only happens when the stream does not match the count prefix, usually
    # because the input was truncated, raise instead of truncating silently.
    if len(values) != total:
        raise ValueError(
            f'[decode_bit2] Value count mismatch: decoded {len(values)} values, prefix declares {total}')
    return values, read
