"""Test support for __future__ annotations."""
from __future__ import annotations

import sys

from inspect import Parameter, signature

import pytest

from incant import Incanter


pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="String annotations not supported"
)


def test_simple_prepare(incanter: Incanter):
    def func(dep1) -> int:
        return dep1 + 1

    with pytest.raises(TypeError):
        incanter.compose_and_call(func)
    assert signature(incanter.compose(func)).parameters == {
        "dep1": Parameter("dep1", Parameter.POSITIONAL_OR_KEYWORD)
    }

    incanter.register_hook(lambda p: p.name == "dep1", lambda: 2)
    assert incanter.compose_and_call(func) == 3

    assert signature(incanter.compose(func)).parameters == {}
    assert signature(incanter.compose(func)).return_annotation is int


def test_reg_by_type(incanter: Incanter):
    @incanter.register_by_type
    def dep(arg: float) -> str:
        return str(arg + 1)

    def fn(arg: str):
        return "1.0" + arg

    assert incanter.compose_and_call(fn, 1.0) == "1.02.0"


def test_incant_pos_args_by_type(incanter: Incanter):
    def func(x: int) -> int:
        return x + 1

    assert incanter.incant(func, 5) == 6
