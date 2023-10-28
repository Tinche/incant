from typing import Literal

import pytest

from incant import Incanter


def test_no_args(incanter: Incanter):
    def func():
        return 1

    assert incanter.incant(func) == 1


def test_no_args_extra_args(incanter: Incanter):
    """Unnecessary arguments are ignored."""

    def func():
        return 1

    assert incanter.incant(func, 3, a=1, b=2)


def test_simple_args(incanter: Incanter):
    def func(a: int, b: int):
        return a + b

    assert incanter.incant(func, a=1, b=1) == 2


def test_pos_args_by_type(incanter: Incanter):
    def func(x: int) -> int:
        return x + 1

    assert incanter.incant(func, 5) == 6


@pytest.mark.asyncio
async def test_async_pos_args_by_type(incanter: Incanter):
    async def func(x: int) -> int:
        return x + 1

    assert await incanter.aincant(func, 5) == 6


def test_missing_args(incanter: Incanter):
    def func(x: int) -> int:
        return x + 1

    with pytest.raises(TypeError):
        incanter.incant(func)


def test_args_with_defaults(incanter: Incanter):
    def func(x: int = 1) -> int:
        return x + 1

    assert incanter.incant(func) == 2

    assert incanter.incant(func, 2) == 3


def test_pos_args_subclasses(incanter: Incanter) -> None:
    """Invoking should handle subclasses of positional args properly."""

    class SubInt(int):
        pass

    def func(x: int) -> int:
        return x + 1

    assert incanter.incant(func, SubInt(2)) == 3


def test_kwargs_subclasses(incanter: Incanter) -> None:
    """Invoking should handle subclasses of kwargs properly."""

    class SubInt(int):
        pass

    def func(x: int) -> int:
        return x + 1

    assert incanter.incant(func, x=SubInt(2)) == 3


def test_adapt(incanter: Incanter):
    """Simple cases of adapt work."""

    def func(x: Literal[0]) -> int:
        return x + 1

    adapted = incanter.adapt(func, lambda p: p.annotation == Literal[0])

    assert adapted(0) == 1
