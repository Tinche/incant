from asyncio import sleep
from collections import OrderedDict
from contextlib import asynccontextmanager
from inspect import Parameter

import pytest

from quattro import TaskGroup

from incant import Incanter


@pytest.mark.asyncio
async def test_async_invoke(incanter: Incanter):
    async def fn():
        await sleep(0.001)
        return 2

    assert (await incanter.ainvoke(fn)) == 2


@pytest.mark.asyncio
async def test_async_dep(incanter: Incanter):
    async def dep1() -> int:
        return 1

    incanter.register_hook(lambda n, _: n == "dep1", dep1)

    with pytest.raises(Exception):
        incanter.invoke(lambda dep1: dep1 + 1) == 2

    assert (await incanter.ainvoke(lambda dep1: dep1 + 1)) == 2
    assert incanter.parameters(lambda dep1: dep1 + 1) == OrderedDict([])


@pytest.mark.asyncio
async def test_async_mixed_dep(incanter: Incanter):
    async def dep1(dep2) -> int:
        return dep2 + 1

    def dep2(input: int) -> int:
        return input + 1

    incanter.register_hook(lambda n, _: n == "dep1", dep1)
    incanter.register_hook(lambda n, _: n == "dep2", dep2)

    with pytest.raises(Exception):
        incanter.invoke(lambda dep1: dep1 + 1, 1)

    assert (await incanter.ainvoke(lambda dep1: dep1 + 1, 1)) == 4
    assert incanter.parameters(lambda dep1: dep1 + 1) == OrderedDict(
        [("input", Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=int))]
    )


@pytest.mark.asyncio
async def test_async_ctx_manager_dep(incanter: Incanter):
    """Async context manager dependencies work."""
    entered, exited = False, False

    @incanter.register_by_name
    @asynccontextmanager
    async def dep1():
        nonlocal entered, exited
        entered = True
        yield 1
        exited = True

    async def fn(dep1: int) -> int:
        nonlocal entered
        return dep1 + 1

    assert (await incanter.ainvoke(fn)) == 2

    assert entered
    assert exited


@pytest.mark.asyncio
async def test_taskgroup_dep(incanter: Incanter):
    """Async context manager dependencies work."""
    incanter.register_by_type(TaskGroup)

    async def fn(tg: TaskGroup):
        return 2

    assert (await incanter.ainvoke(fn)) == 2
