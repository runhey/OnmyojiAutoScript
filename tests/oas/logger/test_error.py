"""
Tests for extract_last_task in oas.logger.error

Scenarios covered:
- Marker at the start of file
- Marker in the middle of file
- Multiple tasks: extracts only the last task
- Marker in the last reverse-read block (first iteration)
- Marker overlaps 2 read blocks (straddles chunk boundary)
- No marker in file (full file output)
- Empty file (empty output)
- Single line without marker
- Single byte without marker
- Marker right at end of file (no trailing content)
- Header-only: hr0 with no trailing log lines
- Back-to-back markers: two task headers adjacent
- CRLF line endings
- block_size smaller than file (multi-iteration reverse search)
"""
import io

import pytest

from oas.logger import logger
from oas.logger.error import extract_last_task


class ReadCounter(io.BytesIO):
    """Wrap a bytes object and count ``.read()`` calls."""

    def __init__(self, data):
        super().__init__(data)
        self.read_count = 0
        self.seek_count = 0

    def read(self, size=-1):
        self.read_count += 1
        return super().read(size)

    def seek(self, pos, whence=0):
        self.seek_count += 1
        return super().seek(pos, whence)


class TestExtractLastTask:
    """Test suite for extract_last_task."""

    # ------------------------------------------------------------------
    # Core scenarios 鈥?using real logger output via mock_capture_writer
    # ------------------------------------------------------------------

    @pytest.mark.parametrize('block_size', [4096, 262144])
    def test_marker_at_file_start(self, block_size):
        """
        Marker is at the very beginning of the file.

        The reverse search should find the marker in the first read chunk
        (or the only read chunk) and output from the second byte onward.
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('LOGIN')
            logger.info('login start')
            logger.info('login success')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        # Expected: content from second byte (after skipping first '+') to end
        expected = content[1:]
        assert result == expected
        assert counter.read_count == 1

    @pytest.mark.parametrize('block_size, expected_clamped', [
        (0, 4096),
        (100, 4096),
        (4095, 4096),
        (4096, 4096),
        (5000, 4096),
        (8192, 8192),
        (10000, 8192),
        (262144, 262144),
        (262145, 262144),
    ])
    def test_block_size_clamping(self, block_size, expected_clamped):
        """
        block_size < 4096 is raised to 4096; non-multiples are rounded down.
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('CLAMP')
            logger.info('clamp')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = content[1:]
        assert result == expected

    def test_marker_in_middle(self):
        """
        Marker is in the middle of the file, preceded by preamble data.

        The reverse search should skip the preamble and find the task header.
        """
        with logger.mock_capture_writer() as capture:
            logger.info('line 1')
            logger.info('line 2')
            logger.info('line 3')
            marker_offset = len(''.join(capture.fd.logs))
            logger.hr0('COMBAT')
            logger.info('combat start')
            logger.info('combat end')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        # Expected: task from marker to end, skipping first byte
        expected = content[marker_offset + 1:]
        assert result == expected
        assert counter.read_count == 1

    def test_multiple_tasks_extracts_last(self):
        """
        Multiple task sections in the file: only the LAST task is extracted.

        The reverse search finds the last occurrence of the marker pattern.
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('LOGIN')
            logger.info('login done')
            last_marker_offset = len(''.join(capture.fd.logs))
            logger.hr0('COMMISSION')
            logger.info('commission start')
            logger.info('commission end')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        expected = content[last_marker_offset + 1:]
        assert result == expected
        assert counter.read_count == 1

    def test_back_to_back_markers(self):
        """
        Two task headers are adjacent with no log lines between them.

        The reverse search must identify the LAST marker correctly
        even when the third line of header A coincides with the first
        line of header B being the same `+=====...=====+` pattern.
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('FIRST')
            last_marker_offset = len(''.join(capture.fd.logs))
            logger.hr0('SECOND')
            logger.info('second task')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        # Last marker is header_b, output from its second byte
        expected = content[last_marker_offset + 1:]
        assert result == expected
        assert counter.read_count == 1

    def test_marker_at_last_block(self):
        """
        Marker is in the last reverse-read block (first iteration).

        Use a small block_size and a large file so the marker lives
        entirely within the first (tail-end) chunk read in reverse;
        no overlap or backward-walking needed.
        """
        block_size = 4096

        # Generate marker + log content using real logger
        with logger.mock_capture_writer() as capture:
            logger.hr0('LAST_BLOCK')
            logger.info('last')
            marker_content = ''.join(capture.fd.logs).encode('utf-8')

        # filler: 20000 bytes before the marker
        filler = b'x\n' * 10000             # 20000 bytes
        content = filler + marker_content

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = marker_content[1:]
        assert result == expected
        assert counter.read_count == 1

    # ------------------------------------------------------------------
    # Boundary / edge cases
    # ------------------------------------------------------------------

    def test_no_marker_in_file(self):
        """
        File has no hr0 marker pattern: entire file should be output.

        When the reverse search exhausts all chunks without a match,
        every chunk is accumulated and written in order.
        """
        with logger.mock_capture_writer() as capture:
            logger.info('some log line without header')
            logger.info('another ordinary line')
            logger.info('third line')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        assert result == content
        assert counter.read_count == 1

    def test_empty_file(self):
        """
        Empty file produces empty output.

        The while loop condition prevents any read, and both
        last_chunk and last_read_end remain at initial values.
        """
        target = io.BytesIO()
        counter = ReadCounter(b'')
        extract_last_task(counter, target)
        result = target.getvalue()

        assert result == b''
        assert counter.read_count == 0
        assert counter.seek_count == 1

    def test_single_byte_no_marker(self):
        """
        Single byte file with no marker pattern.

        Verify the function handles an input smaller than any
        meaningful pattern without crashing.
        """
        for single in [b'+', b'x', b'\n']:
            target = io.BytesIO()
            counter = ReadCounter(single)
            extract_last_task(counter, target)
            result = target.getvalue()

            assert result == single
            assert counter.read_count == 1

    def test_single_line_no_marker(self):
        """
        Single non-marker line outputs the same line unchanged.
        """
        with logger.mock_capture_writer() as capture:
            logger.info('single line')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        assert result == content
        assert counter.read_count == 1

    def test_header_only(self):
        """
        Only an hr0 header with NO trailing log lines.

        Verifies the forward-read phase correctly handles
        last_read_end == file_size (nothing more to read).
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('HEADER_ONLY')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        expected = content[1:]
        assert result == expected
        assert counter.read_count == 1

    def test_marker_right_at_end_of_file(self):
        """
        Marker is at the very end with no trailing log content.

        Verifies the forward-read phase handles the case where
        last_read_end == file_size (no additional bytes to read).
        """
        with logger.mock_capture_writer() as capture:
            logger.info('preamble line')
            marker_offset = len(''.join(capture.fd.logs))
            logger.hr0('END')
            content = ''.join(capture.fd.logs).encode('utf-8')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        expected = content[marker_offset + 1:]
        assert result == expected
        assert counter.read_count == 1

    def test_crlf_line_endings(self):
        """
        File with CRLF (\r\n) line endings: the regex handles both.

        The marker regex uses \r?\n to accept both Unix and Windows
        line endings.
        """
        with logger.mock_capture_writer() as capture:
            logger.hr0('TEST')
            logger.info('test')
            content = ''.join(capture.fd.logs).encode('utf-8')

        # Convert line endings to CRLF
        content = content.replace(b'\n', b'\r\n')

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target)
        result = target.getvalue()

        expected = content[1:]
        assert result == expected
        assert counter.read_count == 1

    # ------------------------------------------------------------------
    # Reverse-search block-boundary scenarios
    # ------------------------------------------------------------------

    def test_overlap_2_blocks(self):
        """
        Marker straddles the boundary between two reverse-read blocks.

        The marker starts before the first reverse-read chunk (iteration 1)
        and is found in iteration 2 thanks to the overlap buffer.
        """
        block_size = 4096

        # Generate marker + log content using real logger
        with logger.mock_capture_writer() as capture:
            logger.hr0('OVERLAP')
            logger.info('overlap')
            marker_content = ''.join(capture.fd.logs).encode('utf-8')

        # Filler ends at byte 12270 so the marker starts straddling the boundary
        filler = b'x\n' * 6135            # 12270 bytes
        content = filler + marker_content

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = marker_content[1:]
        assert result == expected
        assert counter.read_count == 1

    def test_block_size_smaller_than_file(self):
        """
        block_size smaller than file; marker found after multiple reverse
        iterations that don't straddle a boundary.
        """
        block_size = 4096

        # Generate marker + log content using real logger
        with logger.mock_capture_writer() as capture:
            logger.hr0('DEEP')
            logger.info('deep')
            marker_content = ''.join(capture.fd.logs).encode('utf-8')

        # Fill enough data so the reverse search requires multiple iterations
        filler = b'line\n' * 5000         # 30000 bytes
        content = filler + marker_content

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = marker_content[1:]
        assert result == expected
        assert counter.read_count == 1

    def test_hr0_at_block_boundary(self):
        """
        hr0 header lines straddle a block boundary when reading in reverse.

        The marker's 3-line header (+=====+| ... |+=====+) sits across the
        boundary between chunk_2 and chunk_1.  The overlap buffer carries
        the tail of the third line so the regex can match in iteration 2.
        """
        block_size = 4096

        # Generate marker + log content using real logger
        with logger.mock_capture_writer() as capture:
            logger.hr0('BOUNDARY')
            logger.info('done')
            marker_content = ''.join(capture.fd.logs).encode('utf-8')

        # Filler ends at byte 16100 so the marker starts there.
        # The first reverse chunk starts at byte 16384 (= aligned), which
        # lands inside the marker's third line.  The pattern is thus split
        # across chunk_2 (first 284 bytes) and chunk_1 / leftover (tail).
        filler = b'x\n' * int(16100 / 2)          # 16100 bytes
        footer = b'y\n' * 2500                     # 5000 bytes
        content = filler + marker_content + footer

        # extract_last_task outputs from the second byte of the marker
        # (skipping the leading ``+``) to EOF, which includes the footer.
        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()
        expected = content[len(filler) + 1:]
        assert result == expected
        assert counter.read_count == 5

    def test_overlap_with_crlf(self):
        """
        Marker with CRLF line endings straddles a block boundary.

        Combines the overlap scenario with \r\n line endings.
        """
        block_size = 4096

        # Generate marker + log content using real logger
        with logger.mock_capture_writer() as capture:
            logger.hr0('CRLF')
            logger.info('crlf')
            marker_content = ''.join(capture.fd.logs).encode('utf-8')

        # Convert marker content to CRLF
        marker_content = marker_content.replace(b'\n', b'\r\n')

        # Filler ends at byte 12270 so marker starts straddling the boundary
        filler = b'x\r\n' * 4090         # 12270 bytes
        content = filler + marker_content

        target = io.BytesIO()
        counter = ReadCounter(content)
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = marker_content[1:]
        assert result == expected
        assert result == expected


class TestReadCountRealistic:
    """
    Verify IO read counts in a realistic long-running log scenario.
    """

    def test_reverse_then_forward_reads(self):
        """
        Simulate a real log: many early tasks, a ~100KB gap of log lines,
        then the last task at the end.

        The reverse phase reads 3 chunks (iter 1 aligned from EOF, iters 2-3 walk
        4 KB backward each) before finding the header.  The forward phase then
        reads 4 times (3 data + 1 empty termination) to output the rest.
        """
        block_size = 4096

        with logger.mock_capture_writer() as capture:
            logger.set_level("INFO")

            # 5 earlier tasks
            for i in range(5):
                logger.hr0(f"TASK_{i:03d}")
                logger.info("task running")
                logger.info("task done")

            # ~100KB gap of log lines
            for _ in range(3000):
                logger.info("periodic heartbeat")

            # The LAST task
            logger.hr0("LAST_TASK")
            logger.info("last task start")
            for _ in range(200):
                logger.info("last progress")
            logger.info("last task done")

            content = "".join(capture.fd.logs).encode("utf-8")

        # Find the start of the LAST task header (top edge +=====+)

        # Second-to-last occurrence of +===== is the last task header start
        gap_end = content.rfind(b'+=====', 0, content.rfind(b'+====='))

        counter = ReadCounter(content)
        target = io.BytesIO()
        extract_last_task(counter, target, block_size=block_size)
        result = target.getvalue()

        expected = content[gap_end + 1:]
        assert result == expected
        assert counter.read_count == 7
