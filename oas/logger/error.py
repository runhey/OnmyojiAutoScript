import os

from oas.ext.cache import cached_property_threadsafe
from oas.ext.path.atomic import atomic_open


def extract_last_task(src, target_fd, block_size=262144):
    """
    Extract last task from file, each task is startswith hr0()
    Copy logs with minimal IO operations and static memory usage

    Args:
        src (str | io.IOBase): Source file path or a binary file-like object
            (e.g. BytesIO). When a path is given, the file is opened with
            buffering disabled for efficient reverse-seeking.
        target_fd (io.IOBase): Writable binary stream to receive output.
        block_size (int): Read block size in bytes. Defaults to 262144.
            Clamped to ``max(4096, block_size)`` and rounded down to the
            nearest multiple of 4096.
    """
    import re

    # +==================================================================================================+
    # |                                              LOGIN                                               |
    # +==================================================================================================+
    # 2026-01-01 13:33:48.282 | INFO | LOGIN
    regex_marker = re.compile(
        rb'^\+=====[^\r\n]*\r?\n'
        rb'\| [^\r\n]*\r?\n'
        rb'\+=====',
        re.MULTILINE
    )
    alignment = 4096
    overlap_size = 4096

    # Clamp block_size to >= 4096 and round down to the nearest multiple of 4096
    block_size = max(alignment, block_size)
    block_size = (block_size // alignment) * alignment

    # Accept both a file path and an already-open file-like object (e.g. BytesIO)
    if isinstance(src, str):
        # disable buffering, because we are seeking reversely, buffered data is sequential
        src_file = atomic_open(src, 'rb', buffering=0)
    else:
        src_file = src

    try:
        # seek to file end
        file_size = src_file.seek(0, 2)

        pointer = file_size
        leftover = b''
        is_first_chunk = True

        last_read_end = 0
        last_chunk = b''

        # 1. 反向检索阶段
        while pointer > 0:
            if is_first_chunk:
                # 第一次：对齐到 4KB，读取大小可能略大于 block_size
                read_start = max(0, (pointer - block_size) // alignment * alignment)
                is_first_chunk = False
            else:
                # 后续：由于 pointer 已经对齐，读取大小恒等于 block_size
                read_start = max(0, pointer - block_size)

            src_file.seek(read_start)
            # 利用 pointer 直接计算读取长度，完美消灭 read_end 变量
            chunk = src_file.read(pointer - read_start)

            search_buffer = chunk + leftover

            matches = list(regex_marker.finditer(search_buffer))
            if matches:
                last_match = matches[-1]
                idx = last_match.start() + 1

                last_read_end = pointer  # 记录匹配块的物理结束位置
                last_chunk = chunk[idx:]
                break

            # 持续备份状态
            last_read_end = pointer
            last_chunk = chunk

            pointer = read_start  # 移动指针，建立下一次循环的右边界
            leftover = chunk[:overlap_size]

        # 2. 写入检索阶段的最后一个块，也是匹配内容的开头
        target_fd.write(last_chunk)

        # 重新顺着当前物理指针继续向后流式顺序读取
        if last_read_end < file_size:
            while True:
                write_buf = src_file.read(block_size)
                if not write_buf:
                    break
                target_fd.write(write_buf)

    finally:
        src_file.close()


class ErrorZipWriter:
    def __init__(self, file):
        self.file = file

    @cached_property_threadsafe
    def zipfile(self):
        import zipfile
        try:
            return zipfile.ZipFile(self.file, mode='w', compression=zipfile.ZIP_LZMA, compresslevel=6)
        except FileNotFoundError:
            pass
        folder = os.path.dirname(self.file)
        os.makedirs(folder, exist_ok=True)
        return zipfile.ZipFile(self.file, mode='w', compression=zipfile.ZIP_LZMA, compresslevel=6)

    def add_log(self, file, arcname='log.txt'):
        with self.zipfile.open(arcname, mode='w') as target_fd:
            extract_last_task(file, target_fd)

    def add_image(self, image, arcname):
        import zipfile
        self.zipfile.writestr(arcname, image, compress_type=zipfile.ZIP_STORED)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        zipfile = cached_property_threadsafe.pop(self, 'zipfile')
        if zipfile is not None:
            zipfile.close()