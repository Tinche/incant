from collections import OrderedDict
from contextlib import contextmanager
from inspect import Parameter, signature
from sys import version_info

import pytest

from attrs import define

from incant import Incanter, IncantError


def test_simple_dep(incanter: Incanter):
    def func(dep1) -> int:
        return dep1 + 1

    with pytest.raises(TypeError):
        incanter.call(func)
    assert signature(incanter.compose(func)).parameters == {
        "dep1": Parameter("dep1", Parameter.POSITIONAL_OR_KEYWORD)
    }

    incanter.register_hook(lambda p: p.name == "dep1", lambda: 2)
    assert incanter.call(func) == 3

    assert signature(incanter.compose(func)).parameters == {}
    assert signature(incanter.compose(func)).return_annotation is int


def test_nested_deps(incanter: Incanter):
    incanter.register_hook(lambda p: p.name == "dep1", lambda dep2: dep2 + 1)
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1):
        return dep1 + 1

    assert signature(incanter.compose(func)).parameters == {}
    assert incanter.call(func) == 4


def test_nested_partial_deps(incanter: Incanter):
    incanter.register_hook(
        lambda p: p.name == "dep1", lambda dep2, input: dep2 + input + 1
    )
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1):
        return dep1 + 1

    assert signature(incanter.compose(func)).parameters == {
        "input": Parameter("input", Parameter.POSITIONAL_OR_KEYWORD)
    }
    assert incanter.call(func, 1) == 5


def test_nested_partial_deps_with_args(incanter: Incanter):
    incanter.register_hook(
        lambda p: p.name == "dep1", lambda dep2, input: dep2 + input + 1
    )
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1, input2: float) -> float:
        return dep1 + 1 + input2

    assert signature(incanter.compose(func)).parameters == OrderedDict(
        [
            ("input", Parameter("input", Parameter.POSITIONAL_OR_KEYWORD)),
            (
                "input2",
                Parameter("input2", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.call(func, 1, 5.0) == 10.0


def test_nested_partial_deps_with_coalesce(incanter: Incanter):
    @incanter.register_by_type
    def dep(arg: float) -> str:
        return str(arg + 1)

    def fn(arg: str):
        return "1.0" + arg

    assert incanter.call(fn, 1.0) == "1.02.0"


def test_shared_params(incanter: Incanter):
    incanter.register_by_name(lambda dep2, input: dep2 + input + 1, name="dep1")
    incanter.register_by_name(lambda: 2, name="dep2")

    def func(dep1, input: float) -> float:
        return dep1 + 1 + input

    assert signature(incanter.compose(func)).parameters == OrderedDict(
        [
            (
                "input",
                Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.call(func, 5.0) == 14.0


def test_shared_deps_type_from_dep(incanter: Incanter):
    """The parameter type definition comes from the dependency."""

    @incanter.register_by_name
    def dep1(dep2, input: float):
        return dep2 + input + 1

    incanter.register_by_name(lambda: 2, name="dep2")

    def func(dep1, input) -> float:
        return dep1 + 1 + input

    assert signature(incanter.compose(func)).parameters == OrderedDict(
        [
            (
                "input",
                Parameter("input", Parameter.POSITIONAL_OR_KEYWORD, annotation=float),
            ),
        ]
    )
    assert incanter.call(func, 5.0) == 14.0


def test_shared_deps_incompatible(incanter: Incanter):
    """Type incompatibilities are raised."""

    def dep1(dep2, input: str) -> str:
        return dep2 + input + "1"

    incanter.register_hook(lambda p: p.name == "dep1", dep1)
    incanter.register_hook(lambda p: p.name == "dep2", lambda: 2)

    def func(dep1, input: float) -> float:
        return dep1 + 1 + input

    with pytest.raises(IncantError):
        incanter.compose(func)

    with pytest.raises(IncantError):
        incanter.call(func, 5.0)


def test_class_deps(incanter: Incanter):
    @define
    class Dep:
        a: int

    incanter.register_hook(lambda p: p.name == "dep", Dep)
    assert incanter.call(lambda dep: dep.a + 1, a=1)

    assert signature(incanter.compose(lambda dep: dep.a + 1)).parameters == OrderedDict(
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

    with pytest.raises(IncantError):
        incanter.register_by_type(dep)


def test_optional_arg(incanter: Incanter):
    """Registering by type with no return type is an error."""

    @incanter.register_by_name
    def dep(i=1):
        return i

    assert incanter.call(lambda dep: dep + 1) == 2
    assert incanter.call(lambda dep: dep + 1, 2) == 3
    assert signature(incanter.compose(lambda dep: dep + 1)).parameters == {
        "i": Parameter("i", Parameter.POSITIONAL_OR_KEYWORD, default=1)
    }


def test_same_type_arg_coalescing(incanter: Incanter):
    @incanter.register_by_name
    def dep(i: int) -> int:
        return i + 1

    def fn(i: int, dep: int) -> int:
        return i + dep

    assert incanter.call(fn, 1) == 3


def test_shared_deps(incanter: Incanter) -> None:
    @incanter.register_by_name
    def dep1() -> int:
        return 5

    @incanter.register_by_name
    def dep2(dep1: int) -> int:
        return dep1 + 5

    def fn(dep2: int, dep1: int) -> int:
        return dep2 + dep1

    assert incanter.call(fn) == 15


def test_ctx_manager_dep(incanter: Incanter):
    """Context manager dependencies work."""
    entered, exited = False, False

    @incanter.register_by_name(is_ctx_manager="sync")
    @contextmanager
    def dep1():
        nonlocal entered, exited
        assert not entered
        assert not exited
        entered = True
        yield 1
        assert entered
        assert not exited
        exited = True

    def fn(dep1: int) -> int:
        nonlocal entered
        assert entered
        return dep1 + 1

    assert incanter.call(fn) == 2

    assert entered
    assert exited


def test_forced_ctx_manager_dep(incanter: Incanter):
    """Forced context manager dependencies work."""
    entered, exited = False, False

    @incanter.register_by_name(is_ctx_manager="sync")
    @contextmanager
    def dep1():
        nonlocal entered, exited
        assert not entered
        assert not exited
        entered = True
        yield 1
        assert entered
        assert not exited
        exited = True

    def fn(i: int) -> int:
        nonlocal entered
        assert entered
        return i + 1

    assert incanter.compose(fn, forced_deps=[(dep1, "sync")])(1) == 2

    assert entered
    assert exited


def test_ordering(incanter: Incanter) -> None:
    @incanter.register_by_name
    def x() -> int:
        return 1

    @incanter.register_by_name
    def y(x: int) -> int:
        return x + 1

    def func(x: int, y: int) -> int:
        return x + y

    assert incanter.call(func) == 3


def test_parameter_name_overwriting(incanter: Incanter) -> None:
    """Use a hook to replace the parameter name."""

    def func(an_int: int) -> int:
        return an_int + 1

    assert signature(incanter.compose(func)).parameters == {
        "an_int": Parameter("an_int", Parameter.POSITIONAL_OR_KEYWORD, annotation=int)
    }

    def diff_arg_name(another_int: int) -> int:
        return another_int

    incanter.register_by_type(diff_arg_name, int)

    assert incanter.call(func, 1) == 2

    assert signature(incanter.compose(func)).parameters == {
        "another_int": Parameter(
            "another_int", Parameter.POSITIONAL_OR_KEYWORD, annotation=int
        )
    }


@pytest.mark.skipif(
    version_info[:2] <= (3, 9), reason="New union syntax required 3.10+"
)
def test_new_unions(incanter: Incanter) -> None:
    """Parameters with new union syntax work."""

    @incanter.register_by_name
    def provide_int() -> int:
        return 1

    def func(an_int: int | str, provide_int: int) -> int:
        return int(an_int) + provide_int

    prepared = incanter.compose(func)

    # Be careful we don't accidentally optimize this away.
    assert prepared is not func

    assert prepared("1") == 2
