from asyncio import sleep
from collections import OrderedDict
from contextlib import asynccontextmanager
from inspect import Parameter, signature

import pytest

from quattro import TaskGroup

from incant import Incanter


async def test_async_invoke(incanter: Incanter):
    async def fn():
        await sleep(0.001)
        return 2

    assert (await incanter.acompose_and_call(fn)) == 2


async def test_async_dep(incanter: Incanter):
    @incanter.register_by_name
    async def dep1() -> int:
        return 1

    with pytest.raises(TypeError):
        incanter.compose_and_call(lambda dep1: dep1 + 1)

    assert (await incanter.acompose_and_call(lambda dep1: dep1 + 1)) == 2
    assert signature(
        incanter.compose(lambda dep1: dep1 + 1, is_async=True)
    ).parameters == OrderedDict([])


async def test_async_dep_invoke(incanter: Incanter):
    """Same as `test_async_dep`, except use the aliases."""

    @incanter.register_by_name
    async def dep1() -> int:
        return 1

    with pytest.raises(TypeError):
        incanter.invoke(lambda dep1: dep1 + 1)

    assert (await incanter.ainvoke(lambda dep1: dep1 + 1)) == 2
    assert signature(
        incanter.compose(lambda dep1: dep1 + 1, is_async=True)
    ).parameters == OrderedDict([])


async def test_async_mixed_dep(incanter: Incanter):
    @incanter.register_by_name
    async def dep1(dep2) -> int:
        return dep2 + 1

    @incanter.register_by_name(name="dep2")
    def _(input: int) -> int:
        return input + 1

    with pytest.raises(TypeError):
        incanter.compose_and_call(lambda dep1: dep1 + 1, 1)

    assert (await incanter.acompose_and_call(lambda dep1: dep1 + 1, 1)) == 4
    assert signature(
        incanter.compose(lambda dep1: dep1 + 1, is_async=True)
    ).parameters == OrderedDict(
        [("input", Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=int))]
    )


async def test_async_ctx_manager_dep(incanter: Incanter):
    """Async context manager dependencies work."""
    entered, exited = False, False

    @incanter.register_by_name(is_ctx_manager="async")
    @asynccontextmanager
    async def dep1():
        nonlocal entered, exited
        entered = True
        yield 1
        exited = True

    async def fn(dep1: int) -> int:
        nonlocal entered
        return dep1 + 1

    assert (await incanter.acompose_and_call(fn)) == 2

    assert entered
    assert exited


async def test_taskgroup_dep(incanter: Incanter):
    """Async context manager dependencies work."""
    incanter.register_by_type(TaskGroup, is_ctx_manager="async")

    async def fn(tg: TaskGroup):
        assert tg
        return 2

    assert (await incanter.acompose_and_call(fn)) == 2


def test_async_invoke_return_type(incanter: Incanter):
    """Async context manager dependencies work."""

    async def fn() -> int:
        return 2

    assert signature(incanter.compose(fn)).return_annotation is int
