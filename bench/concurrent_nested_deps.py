import asyncio

from typing import Annotated

from di.dependant import Dependant
from di.executors import ConcurrentAsyncExecutor
from di.container import Container, bind_by_type
from incant import Incanter


async def dep2(dep22: int) -> int:
    await asyncio.sleep(0.05)
    return dep22 + 1


async def dep22() -> int:
    await asyncio.sleep(0.001)
    return 1


async def dep1(dep11: int) -> int:
    await asyncio.sleep(0.001)
    return dep11 + 1


async def dep11() -> int:
    await asyncio.sleep(0.05)
    return 1


def incant_func(dep2: int, dep1: int) -> int:
    return dep1 + dep2 + 1


# incant

incant = Incanter()
incant.register_by_name(dep1)
incant.register_by_name(dep11)
incant.register_by_name(dep2)
incant.register_by_name(dep22)


def incant_call_func():
    asyncio.run(incant.ainvoke(incant_func))


# di


async def dep1(dep11: Annotated[int, Dependant(dep11)]) -> int:
    await asyncio.sleep(0.001)
    return dep11 + 1


async def dep2(dep22: Annotated[int, Dependant(dep22)]) -> int:
    await asyncio.sleep(0.001)
    return dep22 + 1


def di_func(
    dep1: Annotated[int, Dependant(dep1)], dep2: Annotated[int, Dependant(dep2)]
) -> None:
    return dep1 + dep2 + 1


container = Container()
executor = ConcurrentAsyncExecutor()
solved = container.solve(Dependant(di_func), scopes=[None])


async def di_execute():
    async with container.enter_scope(None) as state:
        await container.execute_async(solved, state=state, executor=executor)


def di_call_func():
    asyncio.run(di_execute())
