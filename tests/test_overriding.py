from incant import Incanter


def test_simple_override(incanter: Incanter):
    incanter.register_by_type(lambda: 5, type=int)

    def fn(dep1: int):
        return dep1 + 1

    assert incanter.invoke(fn) == 6

    additional_hooks = ((lambda p: p.name == "dep1", lambda _: lambda: 0),)

    assert incanter.prepare(fn, additional_hooks)() == 1
    assert incanter.prepare(fn, additional_hooks)() == 1
    assert incanter.prepare(fn, additional_hooks)() == 1
