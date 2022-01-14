from inspect import Parameter, signature

from incant import Hook, Incanter


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
