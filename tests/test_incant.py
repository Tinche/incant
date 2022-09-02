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

    assert incanter.incant(func, a=1, b=2)


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
