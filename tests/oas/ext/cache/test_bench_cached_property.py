"""
Benchmark: oas cached_property vs functools.cached_property (py3.12+).

The module docstring of oas/ext/cache/cache.py claims that on py3.12 the
self-maintained cached_property is faster than functools.cached_property,
because it writes the computed value back into the instance __dict__ so every
access after the first is a plain attribute read, while functools keeps
routing every access through __get__.

Run with:
    python -m pytest tests/oas/ext/cache/test_bench_cached_property.py --benchmark-only -v
    python -m pytest tests/oas/ext/cache/test_bench_cached_property.py --benchmark-only --benchmark-sort=name -v
"""

import dataclasses as dc
from functools import cached_property as functools_cached_property

import pytest

from oas.ext.cache.cache import (
    cached_class_property,
    cached_property,
    cached_property_threadsafe,
)

IMPLS = {
    "ours": cached_property,
    "functools": functools_cached_property,
}

# =============================================================================
# Class builders
# =============================================================================


def _build_class(impl, nattrs, tag="C"):
    """Dynamically build a class with ``nattrs`` cached properties."""
    funcs = {}
    for i in range(nattrs):
        name = f"a{i}"

        def calc(_self, _i=i):
            return _i

        calc.__name__ = name
        funcs[name] = impl(calc)
    return type(f"{tag}_{getattr(impl, '__name__', impl)}_{nattrs}", (), funcs)


def _build_classmethod_plain(nattrs):
    funcs = {}
    for i in range(nattrs):
        name = f"a{i}"

        def calc(_self, _i=i):
            return _i

        calc.__name__ = name
        funcs[name] = property(calc)
    return type(f"Ref_property_{nattrs}", (), funcs)


def _build_plain(nattrs):
    """Plain instance attributes, the lower-bound reference (pure dict get)."""
    funcs = {}
    for i in range(nattrs):
        funcs[f"a{i}"] = i
    return type(f"Ref_plain_{nattrs}", (), funcs)


def _attrs(n):
    return [f"a{i}" for i in range(n)]


# =============================================================================
# Warm-state hit benchmarks: access cached values only
# =============================================================================


def _bench_hit(benchmark, impl, nattrs, ninst, hits):
    cls = _build_class(impl, nattrs)
    objs = [cls() for _ in range(ninst)]
    attrs = _attrs(nattrs)
    for o in objs:  # warm everything up
        for a in attrs:
            getattr(o, a)

    def loop():
        acc = 0
        for _ in range(hits):
            for o in objs:
                for a in attrs:
                    acc += getattr(o, a)
        return acc

    benchmark(loop)


@pytest.mark.parametrize("impl", ["ours", "functools"])
@pytest.mark.parametrize("nattrs", [1, 4, 16])
def test_hit_20_insts(benchmark, impl, nattrs):
    """Warm hits: the claim that second+ access is a plain dict read."""
    _bench_hit(benchmark, IMPLS[impl], nattrs, ninst=20, hits=25)


@pytest.mark.parametrize("impl", ["ours", "functools"])
@pytest.mark.parametrize("ninst", [1, 10, 100])
def test_hit_many_instances(benchmark, impl, ninst):
    """Warm hits with growing instance count (1 attr each)."""
    _bench_hit(benchmark, IMPLS[impl], nattrs=1, ninst=ninst, hits=10)


def test_hit_reference_plain_attr(benchmark):
    """Lower bound: plain instance attribute (pure dict access)."""
    cls = _build_plain(1)
    obj = cls()
    obj.a0

    def loop():
        acc = 0
        for _ in range(250):
            acc += obj.a0
        return acc

    benchmark(loop)


def test_hit_reference_builtin_property(benchmark):
    """Reference: builtin @property routes every access through __get__."""
    cls = _build_classmethod_plain(1)
    obj = cls()

    def loop():
        acc = 0
        for _ in range(250):
            acc += obj.a0
        return acc

    benchmark(loop)


# =============================================================================
# Cold benchmarks: first access computes the value
# =============================================================================


def _bench_cold(benchmark, impl, nattrs):
    cls = _build_class(impl, nattrs)
    attrs = _attrs(nattrs)

    def loop():
        o = cls()
        acc = 0
        for a in attrs:
            acc += getattr(o, a)
        return acc

    benchmark(loop)


@pytest.mark.parametrize("impl", ["ours", "functools"])
@pytest.mark.parametrize("nattrs", [1, 8])
def test_cold_first_access(benchmark, impl, nattrs):
    """Cold: build a fresh instance and touch each property once."""
    _bench_cold(benchmark, IMPLS[impl], nattrs)


# =============================================================================
# Mixed benchmark: one cold access followed by warm hits
# =============================================================================


@pytest.mark.parametrize("impl", ["ours", "functools"])
@pytest.mark.parametrize("nattrs", [1, 8])
def test_mixed_cold_then_hits(benchmark, impl, nattrs):
    """Real usage: first access computes, the rest hits the cache."""
    cls = _build_class(IMPLS[impl], nattrs)
    attrs = _attrs(nattrs)

    def loop():
        o = cls()
        acc = 0
        for a in attrs:
            acc += getattr(o, a)
        for _ in range(20):
            for a in attrs:
                acc += getattr(o, a)
        return acc

    benchmark(loop)


# =============================================================================
# dataclass scenario
# =============================================================================


def _build_dataclass(impl, nattrs):
    funcs = {}
    for i in range(nattrs):
        name = f"a{i}"

        def calc(_self, _i=i):
            return _i

        calc.__name__ = name
        funcs[name] = impl(calc)
    return dc.dataclass(type(f"Data_{getattr(impl, '__name__', impl)}_{nattrs}", (), funcs))


@pytest.mark.parametrize("impl", ["ours", "functools"])
@pytest.mark.parametrize("nattrs", [1, 4])
def test_dataclass_hit(benchmark, impl, nattrs):
    """dataclass instances, warm hits."""
    cls = _build_dataclass(IMPLS[impl], nattrs)
    objs = [cls() for _ in range(20)]
    attrs = _attrs(nattrs)
    for o in objs:
        for a in attrs:
            getattr(o, a)

    def loop():
        acc = 0
        for _ in range(25):
            for o in objs:
                for a in attrs:
                    acc += getattr(o, a)
        return acc

    benchmark(loop)


# =============================================================================
# Thread-safe variant: its per-access lock cost
# =============================================================================


@pytest.mark.parametrize("impl", ["ours", "threadsafe"])
def test_threadsafe_lock_overhead(benchmark, impl):
    """Cold + warm hits: what does the per-instance lock cost vs plain?"""
    impl_cls = cached_property if impl == "ours" else cached_property_threadsafe
    cls = _build_class(impl_cls, 1)
    objs = [cls() for _ in range(20)]
    for o in objs:
        o.a0

    def loop():
        acc = 0
        for o in objs:
            acc += o.a0
        return acc

    benchmark(loop)


# =============================================================================
# Class-level cached property
# =============================================================================


def test_cached_class_property_hit(benchmark):
    """Warm hits on a cached_class_property (no functools counterpart)."""

    class Klass:
        @cached_class_property
        def shared(cls):
            return 1

    Klass.shared
    for _ in range(10):
        assert Klass.shared == 1

    def loop():
        acc = 0
        for _ in range(250):
            acc += Klass.shared
        return acc

    benchmark(loop)


def test_cached_class_property_cold(benchmark):
    """Cold: first touch computes and writes into the class dict."""

    def loop():
        class Klass:
            @cached_class_property
            def shared(cls):
                return 1

        return Klass.shared

    benchmark(loop)