from contextlib import asynccontextmanager

import pytest

from incant import Incanter


def test_noarg_forced_dep(incanter: Incanter):
    def forced_dep():
        raise ValueError()

    def fn():
        return 1

    with pytest.raises(ValueError):
        prep = incanter.prepare(fn, forced_deps=(forced_dep,))
        prep()


def test_simple_arg_forced_dep(incanter: Incanter):
    val = 5

    def forced_dep(i: int):
        assert i == val
        raise ValueError()

    def fn():
        return 1

    with pytest.raises(ValueError):
        prep = incanter.prepare(fn, forced_deps=(forced_dep,))
        prep(val)


def test_complex_arg_forced_dep(incanter: Incanter):
    val = 5
    val_f = 10.0

    def forced_dep(i: int) -> None:
        assert i == val

    def fn(f: float):
        assert f == val_f
        return 1

    prep = incanter.prepare(fn, forced_deps=(forced_dep,))
    assert prep(val, val_f) == 1


def test_shared_args(incanter: Incanter):
    val = 5

    def forced_dep(i: int) -> None:
        assert i == val

    def fn(i: int):
        assert i == val
        return 1

    prep = incanter.prepare(fn, forced_deps=(forced_dep,))
    assert prep(val) == 1


def test_shared_dep(incanter: Incanter):
    val = 5

    def forced_dep(i: int) -> None:
        assert i == val

    def fn(i: int):
        assert i == val
        return 1

    @incanter.register_by_type
    def dep() -> int:
        return val

    prep = incanter.prepare(fn, forced_deps=(forced_dep,))
    assert prep() == 1


async def test_async_ctx_mgr_dep(incanter: Incanter):
    before = False
    after = False

    def fn(i: int):
        nonlocal before, after
        assert before
        assert not after
        assert i == 5
        return 1

    @asynccontextmanager
    async def my_async_context_mgr():
        nonlocal before, after
        assert not before
        assert not after
        before = True

        yield None

        assert before
        assert not after
        after = True

    prep = incanter.prepare(
        fn, is_async=True, forced_deps=((my_async_context_mgr, "async"),)
    )
    assert await prep(5) == 1


async def test_async_ctx_mgr_with_param(incanter: Incanter):
    before = False
    after = False

    def fn(i: int):
        nonlocal before, after
        assert before
        assert not after
        assert i == 5
        return 1

    @asynccontextmanager
    async def my_async_context_mgr(f: float):
        nonlocal before, after

        assert f == 10.0
        assert not before
        assert not after
        before = True

        yield None

        assert before
        assert not after
        after = True

    prep = incanter.prepare(
        fn, is_async=True, forced_deps=((my_async_context_mgr, "async"),)
    )
    assert await prep(10.0, 5) == 1


async def test_async_ctx_mgr_with_shared_param_and_dep(incanter: Incanter):
    before = False
    after = False

    @incanter.register_by_type
    def dep1() -> int:
        return 5

    def fn(i: int, f: float):
        nonlocal before, after
        assert before
        assert not after
        assert i == 5
        assert f == 10.0
        return 1

    @asynccontextmanager
    async def my_async_context_mgr(my_int: int, f: float):
        nonlocal before, after

        assert my_int == 5
        assert f == 10.0
        assert not before
        assert not after
        before = True

        yield None

        assert before
        assert not after
        after = True

    prep = incanter.prepare(fn, forced_deps=((my_async_context_mgr, "async"),))
    assert await prep(10.0) == 1
