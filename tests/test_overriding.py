from inspect import Parameter, signature


try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated  # type: ignore

from incant import Hook, Incanter, Override


def test_simple_override(incanter: Incanter):
    incanter.register_by_type(lambda: 5, type=int)

    def fn(dep1: int):
        return dep1 + 1

    assert incanter.invoke(fn) == 6

    additional_hooks = [Hook.for_name("dep1", lambda: 0)]

    assert incanter.prepare(fn, additional_hooks)() == 1
    assert incanter.prepare(fn, additional_hooks)() == 1
    assert incanter.prepare(fn, additional_hooks)() == 1

    additional_hooks = [Hook.for_type(int, lambda: 10)]

    assert incanter.prepare(fn, additional_hooks)() == 11
    assert incanter.prepare(fn, additional_hooks)() == 11


def test_override_to_parameter(incanter: Incanter):
    """A dependency can be overriden to a parameter."""
    incanter.register_by_type(lambda: 5, type=int)

    def fn(dep1: int):
        return dep1 + 1

    assert incanter.invoke(fn) == 6

    additional_hooks = [Hook.for_name("dep1", None)]

    assert signature(incanter.prepare(fn, additional_hooks)).parameters == {
        "dep1": Parameter("dep1", Parameter.POSITIONAL_OR_KEYWORD, annotation=int)
    }
    assert signature(incanter.prepare(fn)).parameters == {}


def test_individial_param_overriding_name(incanter: Incanter):
    """A function param can be overridden."""
    incanter.register_by_name(lambda: 5, name="dep2")

    def fn(dep1: Annotated[int, Override(name="dep2")]):
        return dep1

    assert incanter.invoke(fn) == 5


def test_individial_param_overriding_type(incanter: Incanter):
    """A function param can be overridden."""
    incanter.register_by_type(lambda: 5, type=int)

    def fn(dep1: Annotated[str, Override(annotation=int)]):
        return dep1

    assert incanter.invoke(fn) == 5
