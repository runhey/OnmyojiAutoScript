"""
Mock of the file object returned by open().

The file content lives in the shared FakeFile record, so writes are
visible to every other open handle of the same file, and a replaced
file keeps its old content for already open handles. The record is a
shared state: the operations that touch the content take the state lock
of the filesystem (the same lock as every filesystem operation).
"""
import io
import os

from .base import synchronized


class FakeFileObject:
    """
    Mock of the file object returned by open().

    Supports the common file operations: read / readline / readlines /
    readinto / write / writelines / seek / tell / truncate / flush /
    close / fileno / iteration and the context manager protocol.
    Text mode operations decode the shared content on demand, so writes
    through other handles of the same file are visible, and multi-byte
    encodings and newline translation work.
    """
    __slots__ = (
        '_fs', '_entry', '_mode_str', '_binary', '_readable', '_writable',
        '_append', '_encoding', '_errors', '_newline', '_fd', '_closed',
        '_pos', '_lock',
    )

    def __init__(self, fs, entry, mode, binary, readable, writable, append,
                 position, encoding, errors, newline, fd):
        """
        Args:
            fs (FakeFilesystem): Owner filesystem, for fd registration
            entry (FakeFile): File record, the content storage
            mode (str): Open mode, e.g. "rb"
            binary (bool): Whether the file is opened in binary mode
            readable (bool): Whether reading is allowed
            writable (bool): Whether writing is allowed
            append (bool): Whether writes always go to the end
            position (int): Initial position, bytes in binary mode.
                Text mode positions are only used for non-append modes.
            encoding (str): Text encoding, None in binary mode
            errors (str): Error handling of encoding
            newline (str): Newline handling of text mode
            fd (int): Fake file descriptor number
        """
        self._fs = fs
        self._entry = entry
        self._mode_str = mode
        self._binary = binary
        self._readable = readable
        self._writable = writable
        self._append = append
        self._encoding = encoding
        self._errors = errors
        self._newline = newline
        self._fd = fd
        self._closed = False
        self._pos = position
        # the state lock of the filesystem, taken by every operation that
        # touches the shared record
        self._lock = fs._lock

    """
    Attributes
    """

    @property
    def name(self):
        """
        Returns:
            str: Path of the file
        """
        return self._entry.path

    @property
    def mode(self):
        """
        Returns:
            str: Open mode, e.g. "rb"
        """
        return self._mode_str

    @property
    def closed(self):
        """
        Returns:
            bool: Whether the file is closed
        """
        return self._closed

    @property
    def encoding(self):
        """
        Returns:
            str: Text encoding, None in binary mode
        """
        return self._encoding

    @property
    def errors(self):
        """
        Returns:
            str: Error handling of encoding, None in binary mode
        """
        return self._errors

    @property
    def newlines(self):
        """
        Returns:
            str: Newline handling of text mode, None in binary mode
        """
        return self._newline

    def __repr__(self):
        if self._binary:
            return f'<_io.BufferedReader name={self.name!r}>'
        else:
            return (
                f'<_io.TextIOWrapper name={self.name!r} mode={self._mode_str!r} '
                f'encoding={self._encoding!r}>'
            )

    """
    Internal helpers
    """

    def _check_open(self):
        if self._closed:
            raise ValueError('I/O operation on closed file')

    def _get_view(self):
        """
        Decode the current content, translating newlines per the mode.

        The view is computed on demand, so writes through other handles
        of the same file are visible.

        Returns:
            str: Decoded and translated text view
        """
        text = self._entry.content.decode(self._encoding, self._errors)
        if self._newline is None:
            # universal newlines: translate to "\n"
            text = text.replace('\r\n', '\n').replace('\r', '\n')
        return text

    def _flush_view(self, view):
        """
        Write a text view back to the record content.

        The read translation is reversed: "\n" is translated back to the
        platform line separator, like the real write translation.

        Args:
            view (str): Text view to write
        """
        if self._newline is None:
            raw = view.replace(os.linesep, '\n')
        else:
            raw = view
        self._entry.content = raw.encode(self._encoding, self._errors)

    """
    Read
    """

    @synchronized
    def read(self, size=-1):
        """
        Read data from the current position.

        Args:
            size (int): Maximum bytes / characters to read.
                Defaults to -1, read to the end.

        Returns:
            str | bytes: Read data, empty at the end of the file
        """
        self._check_open()
        if not self._readable:
            raise io.UnsupportedOperation('not readable')
        if self._binary:
            content = self._entry.content
            if size is None or size < 0:
                if self._pos == 0:
                    # read all from the start, return the content as-is
                    data = content
                else:
                    data = content[self._pos:]
            else:
                data = content[self._pos:self._pos + size]
            self._pos += len(data)
            return data
        else:
            view = self._get_view()
            if size is None or size < 0:
                if self._pos == 0:
                    data = view
                else:
                    data = view[self._pos:]
            else:
                data = view[self._pos:self._pos + size]
            self._pos += len(data)
            return data

    @synchronized
    def readline(self, size=-1):
        """
        Read one line from the current position, the line ending is included.

        Args:
            size (int): Maximum bytes / characters to read.
                Defaults to -1, read to the line ending.

        Returns:
            str | bytes: Read line, empty at the end of the file
        """
        self._check_open()
        if not self._readable:
            raise io.UnsupportedOperation('not readable')
        if self._binary:
            content = self._entry.content
            data = content[self._pos:]
            if size is not None and size >= 0:
                data = data[:size]
            index = data.find(b'\n')
            if index < 0:
                self._pos += len(data)
                return data
            else:
                self._pos += index + 1
                return data[:index + 1]
        else:
            view = self._get_view()
            data = view[self._pos:]
            if size is not None and size >= 0:
                data = data[:size]
            index = data.find('\n')
            if index < 0:
                self._pos += len(data)
                return data
            else:
                self._pos += index + 1
                return data[:index + 1]

    @synchronized
    def readlines(self, hint=-1):
        """
        Read all lines from the current position.

        Args:
            hint (int): Stop reading when the accumulated size reaches
                the hint. Defaults to -1, read all lines.

        Returns:
            list[str] | list[bytes]: Read lines
        """
        lines = []
        total = 0
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
            total += len(line)
            if hint > 0 and total >= hint:
                break
        return lines

    @synchronized
    def readinto(self, buffer):
        """
        Read bytes into the given buffer, binary mode only.

        Args:
            buffer (bytearray | memoryview): Buffer to fill

        Returns:
            int: Number of bytes read
        """
        self._check_open()
        if not self._readable:
            raise io.UnsupportedOperation('not readable')
        if not self._binary:
            raise io.UnsupportedOperation('readinto() not supported in text mode')
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    """
    Write
    """

    @synchronized
    def write(self, data):
        """
        Write data at the current position, or at the end in append mode.

        Args:
            data (str | bytes): Data to write

        Returns:
            int: Number of bytes / characters written
        """
        self._check_open()
        if not self._writable:
            raise io.UnsupportedOperation('not writable')
        if self._binary:
            if isinstance(data, str):
                raise TypeError(f'a bytes-like object is required, not {type(data).__name__!r}')
            data = bytes(data)
            content = self._entry.content
            if self._append:
                self._entry.content = content + data
            else:
                pos = self._pos
                if pos > len(content):
                    # writing beyond the end pads with zeros
                    content = content + b'\x00' * (pos - len(content))
                self._entry.content = content[:pos] + data + content[pos + len(data):]
                self._pos = pos + len(data)
            return len(data)
        else:
            if not isinstance(data, str):
                raise TypeError(f'write() argument must be str, not {type(data).__name__}')
            if self._newline is None:
                # translate "\n" to the platform line separator
                written = data.replace('\n', os.linesep)
            else:
                written = data
            view = self._get_view()
            if self._append:
                pos = len(view)
            else:
                pos = self._pos
            # overwrite len(data) characters at the position
            view = view[:pos] + written + view[pos + len(data):]
            self._flush_view(view)
            self._pos = pos + len(data)
            return len(data)

    def writelines(self, lines):
        """
        Write a list of lines to the file.

        Args:
            lines (Iterable[str] | Iterable[bytes]): Lines to write
        """
        for line in lines:
            self.write(line)

    @synchronized
    def truncate(self, size=None):
        """
        Truncate the file at the given size, or the current position.

        Args:
            size (int): Size to truncate to. Defaults to None, use the
                current position.

        Returns:
            int: The new size
        """
        self._check_open()
        if not self._writable:
            raise io.UnsupportedOperation('not writable')
        if size is None:
            size = self._pos
        if self._binary:
            content = self._entry.content
            if size < len(content):
                content = content[:size]
            elif size > len(content):
                # growing truncate pads with zeros
                content = content + b'\x00' * (size - len(content))
            self._entry.content = content
        else:
            view = self._get_view()
            if size < len(view):
                view = view[:size]
            elif size > len(view):
                view = view + '\x00' * (size - len(view))
            self._flush_view(view)
        return size

    def flush(self):
        """
        Flush the file, a no-op because content is written in memory.
        """
        self._check_open()

    """
    Position
    """

    @synchronized
    def seek(self, offset, whence=0):
        """
        Move the position.

        Args:
            offset (int): Offset to seek to
            whence (int): 0 for the start, 1 for the current position,
                2 for the end. Defaults to 0.
                Text mode only allows seeking from the start.

        Returns:
            int: The new position
        """
        self._check_open()
        if self._binary:
            if whence == 0:
                pos = offset
            elif whence == 1:
                pos = self._pos + offset
            elif whence == 2:
                pos = len(self._entry.content) + offset
            else:
                raise ValueError(f'invalid whence ({whence}, should be 0, 1 or 2)')
            self._pos = max(0, pos)
        else:
            if whence == 0:
                if offset < 0:
                    raise ValueError('negative seek position')
                pos = offset
            elif whence == 1:
                if offset:
                    raise ValueError('seek() not available in text mode, only the start can be sought')
                pos = self._pos
            elif whence == 2:
                if offset:
                    raise ValueError('seek() not available in text mode, only the start can be sought')
                pos = len(self._get_view())
            else:
                raise ValueError(f'invalid whence ({whence}, should be 0, 1 or 2)')
            self._pos = pos
        return self._pos

    def tell(self):
        """
        Returns:
            int: The current position, bytes in binary mode,
                characters in text mode
        """
        self._check_open()
        return self._pos

    """
    Descriptor and state
    """

    def fileno(self):
        """
        Returns:
            int: Fake file descriptor number, usable with the mocked
                os.fstat()
        """
        self._check_open()
        return self._fd

    def isatty(self):
        """
        Returns:
            bool: Always False
        """
        self._check_open()
        return False

    def readable(self):
        """
        Returns:
            bool: Whether the file is opened for reading
        """
        self._check_open()
        return self._readable

    def writable(self):
        """
        Returns:
            bool: Whether the file is opened for writing
        """
        self._check_open()
        return self._writable

    def seekable(self):
        """
        Returns:
            bool: Always True
        """
        self._check_open()
        return True

    @synchronized
    def close(self):
        """
        Close the file and release the file descriptor.
        """
        if self._closed:
            return
        self._closed = True
        self._fs._fds.pop(self._fd, None)

    """
    Context manager and iteration
    """

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __iter__(self):
        self._check_open()
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line
