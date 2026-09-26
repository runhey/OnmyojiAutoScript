"""
Benchmark: msgspec.Struct -> dataclass(slots=True) record migration of the fake filesystem.

Run with:  pytest tests/oas/testing/filesystem/test_benchmark.py -s

- Micro: same-shape records (msgspec vs dataclass) in isolation,
  the per-operation cost of the record layer itself. Fully self-contained.
- Macro: the OAS fake filesystem under a typical workload, end-to-end
  absolute timing. Single-sided baseline; the migration comparison is
  carried by the micro part.

No external project is imported. No performance assertions are made;
numbers are printed for inspection.
"""
import os
import stat as statmod
import timeit

import pytest
from dataclasses import dataclass

import msgspec

from oas.testing.filesystem import FakeFilesystem as OasFFS  # dataclass version


def _build_stat(st_mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime):
    """Same shape as oas/testing/filesystem/base.py::_build_stat."""
    return os.stat_result((st_mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime))


# ---------------------------------------------------------------------------
# same-shape records (fields/defaults/stat copied verbatim from base.py)
# ---------------------------------------------------------------------------

class MsgsFile(msgspec.Struct):
    path: str
    content: bytes = b''
    mode: int = 0o666
    ino: int = 0
    dev: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime: float = 0.0
    mtime: float = 0.0
    ctime: float = 0.0

    def stat(self):
        return _build_stat(
            statmod.S_IFREG | self.mode, self.ino, self.dev, self.nlink,
            self.uid, self.gid, len(self.content), self.atime, self.mtime, self.ctime,
        )


@dataclass(slots=True)
class DataclassFile:
    path: str
    content: bytes = b''
    mode: int = 0o666
    ino: int = 0
    dev: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    atime: float = 0.0
    mtime: float = 0.0
    ctime: float = 0.0

    def stat(self):
        return _build_stat(
            statmod.S_IFREG | self.mode, self.ino, self.dev, self.nlink,
            self.uid, self.gid, len(self.content), self.atime, self.mtime, self.ctime,
        )


# ---------------------------------------------------------------------------
# micro: run() executes `total` operations on the record class `C`
# ---------------------------------------------------------------------------

def run_construct(C, total):
    for _ in range(total):
        C('C:/x/a.txt')


def run_attr_read(C, total):
    o = C('C:/x/a.txt')
    for _ in range(total):
        _ = o.path
        _ = o.content


def run_attr_write(C, total):
    o = C('C:/x/a.txt')
    for _ in range(total):
        o.mode = 0o600
        o.content = b'x'


def run_stat(C, total):
    o = C('C:/x/a.txt')
    for _ in range(total):
        _ = o.stat()


def _time(run, C, total, repeat=9):
    """Best wall time of `total` operations, in ns/op."""
    best = min(timeit.repeat(lambda: run(C, total), number=1, repeat=repeat))
    return best / total * 1e9


def test_micro_report():
    """Record-layer cost: msgspec vs dataclass, per operation in ns."""
    total = 20000
    rows = [
        ('construct', run_construct),
        ('attr read', run_attr_read),
        ('attr write', run_attr_write),
        ('stat()', run_stat),
    ]
    header = f"{'operation':<12} {'msgspec':>9} {'dataclass':>10} {'dc/ms':>7}"
    print()
    print('=== micro: record layer, ns/op (smaller is better) ===')
    print(header)
    for label, run in rows:
        ms = _time(run, MsgsFile, total)
        dc = _time(run, DataclassFile, total)
        ratio = dc / ms * 100
        print(f"{label:<12} {ms:>9.1f} {dc:>10.1f} {ratio:>6.1f}%")


# ---------------------------------------------------------------------------
# macro: single-sided absolute timing of the OAS fake filesystem
# ---------------------------------------------------------------------------

def _macro_mixed():
    """Mixed everyday use: build tree, touch files, stat, move, delete."""
    with OasFFS() as fs:
        root = fs.root_dir.path
        folder = f'{root}/a/b'
        n = 200
        for i in range(n):
            fs.create_file(f'{folder}/f{i}.txt', contents=b'x' * 32)
        for i in range(n):
            path = f'{folder}/f{i}.txt'
            with open(path, 'r+b') as f:
                f.write(b'y')
            with open(path, 'rb') as f:
                assert len(f.read()) == 32
            assert os.path.exists(path)
            assert os.path.isfile(path)
            st = os.stat(path)
            assert statmod.S_ISREG(st.st_mode)
        os.rename(f'{folder}/f0.txt', f'{folder}/renamed.txt')
        os.replace(f'{folder}/f1.txt', f'{folder}/renamed.txt')
        assert not os.path.exists(f'{folder}/f1.txt')
        fs.rmtree(f'{root}/a')
        assert not fs.exists(f'{root}/a')


def _macro_create_storm():
    """Construction-heavy: create 1000 files, never touch the content.
    The record constructor is the dominant cost here."""
    with OasFFS() as fs:
        root = fs.root_dir.path
        for i in range(1000):
            fs.create_file(f'{root}/s/f{i}.txt')


def _macro_io_storm():
    """IO-heavy: rewrite and reread the same file repeatedly.
    The file object (attr write) is the dominant cost here."""
    with OasFFS() as fs:
        root = fs.root_dir.path
        path = f'{root}/a.bin'
        fs.create_file(path)
        payload = b'data' * 100
        for _ in range(50):
            with open(path, 'wb') as f:
                f.write(payload)
            with open(path, 'rb') as f:
                assert f.read() == payload


def _macro_stat_storm():
    """Query-heavy: repeated stat and getsize on existing files."""
    with OasFFS() as fs:
        root = fs.root_dir.path
        for i in range(200):
            fs.create_file(f'{root}/f{i}.txt', contents=b'x')
        for _ in range(64):
            for j in range(200):
                st = os.stat(f'{root}/f{j}.txt')
                assert statmod.S_ISREG(st.st_mode)
                _ = os.path.getsize(f'{root}/f{j}.txt')


def test_macro_report():
    """Four workloads on the OAS fake filesystem, best/median of 9 runs in ms."""
    scenarios = [
        ('mixed everyday', _macro_mixed, 9),
        ('construct storm', _macro_create_storm, 9),
        ('io storm', _macro_io_storm, 9),
        ('stat storm', _macro_stat_storm, 9),
    ]
    print()
    print('=== macro: full fake-fs workloads on OAS (dataclass), ms ===')
    print(f"{'workload':<18} {'best':>8} {'median':>8} {'runs':>5}")
    for label, fn, repeat in scenarios:
        times = sorted(timeit.repeat(fn, number=1, repeat=repeat))
        best = times[0] * 1000
        median = times[len(times) // 2] * 1000
        print(f"{label:<18} {best:>8.2f} {median:>8.2f} {len(times):>5}")