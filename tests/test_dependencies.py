from collections import OrderedDict
from inspect import Parameter, signature

import pytest

from attr import define

from incant import Incanter


def test_simple_dep(incanter: Incanter):
    def func(dep1):
        return dep1 + 1

    with pytest.raises(TypeError):
        incanter.invoke(func)
    assert signature(incanter.prepare(func)).parameters == {
        "dep1": Parameter("dep1", Parameter.POSITIONAL_OR_KEYWORD)
    }

    incanter.register_hook(lambda p: p.name == "dep1", lambda: 2)
    assert incanter.invoke(func) == 3

    assert signature(incanter.prepare(func)).parameters == {}


def test_nested_deps(incanter: Incanter):
    incanter.register_hook(lambda p: p.name == "dep1", lambda dep2: dep2 + 1)
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1):
        return dep1 + 1

    assert signature(incanter.prepare(func)).parameters == {}
    assert incanter.invoke(func) == 4


def test_nested_partial_deps(incanter: Incanter):
    incanter.register_hook(
        lambda p: p.name == "dep1", lambda dep2, input: dep2 + input + 1
    )
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1):
        return dep1 + 1

    assert signature(incanter.prepare(func)).parameters == {
        "input": Parameter("input", Parameter.POSITIONAL_OR_KEYWORD)
    }
    assert incanter.invoke(func, 1) == 5


def test_nested_partial_deps_with_args(incanter: Incanter):
    incanter.register_hook(
        lambda p: p.name == "dep1", lambda dep2, input: dep2 + input + 1
    )
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1, input2: float) -> float:
        return dep1 + 1 + input2

    assert signature(incanter.prepare(func)).parameters == OrderedDict(
        [
            ("input", Parameter("input", Parameter.POSITIONAL_OR_KEYWORD)),
            (
                "input2",
                Parameter("input2", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.invoke(func, 1, 5.0) == 10.0


def test_shared_deps(incanter: Incanter):
    incanter.register_by_name(lambda dep2, input: dep2 + input + 1, name="dep1")
    incanter.register_by_name(lambda: 2, name="dep2")

    def func(dep1, input: float) -> float:
        return dep1 + 1 + input

    assert signature(incanter.prepare(func)).parameters == OrderedDict(
        [
            (
                "input",
                Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.invoke(func, 5.0) == 14.0


def test_shared_deps_type_from_dep(incanter: Incanter):
    """The parameter type definition comes from the dependency."""

    @incanter.register_by_name
    def dep1(dep2, input: float):
        return dep2 + input + 1

    incanter.register_by_name(lambda: 2, name="dep2")

    def func(dep1, input) -> float:
        return dep1 + 1 + input

    assert signature(incanter.prepare(func)).parameters == OrderedDict(
        [
            (
                "input",
                Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.invoke(func, 5.0) == 14.0


def test_shared_deps_incompatible(incanter: Incanter):
    """Type incompatibilities are raised."""

    def dep1(dep2, input: str) -> str:
        return dep2 + input + "1"

    incanter.register_hook(lambda p: p.name == "dep1", dep1)
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1, input: float) -> float:
        return dep1 + 1 + input

    with pytest.raises(Exception):
        incanter.prepare(func)

    with pytest.raises(Exception):
        incanter.invoke(func, 5.0)


def test_class_deps(incanter: Incanter):
    @define
    class Dep:
        a: int

    incanter.register_hook(lambda p: p.name == "dep", Dep)
    assert incanter.invoke(lambda dep: dep.a + 1, a=1)

    assert signature(incanter.prepare(lambda dep: dep.a + 1)).parameters == OrderedDict(
        [
            (
                "a",
                Parameter("a", Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
            ),
        ]
    )


def test_no_return_type(incanter: Incanter):
    """Registering by type with no return type is an error."""

    def dep():
        return 1

    with pytest.raises(Exception):
        incanter.register_by_type(dep)
