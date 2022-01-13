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
