from incant import Incanter


def test_no_deps(incanter: Incanter) -> None:
    """Original function should be returned."""

    def func() -> int:
        return 1

    assert incanter.prepare(func) == func


def test_some_deps(incanter: Incanter) -> None:
    """Original function should be returned."""

    def func(x: int) -> int:
        return x + 1

    assert incanter.prepare(func) == func


def test_forced_deps(incanter: Incanter) -> None:
    """
    Original function should not be returned, because there is a
    forced dependency.
    """

    def func(x: int) -> int:
        return x + 1

    def dep1() -> None:
        return

    assert incanter.prepare(func, forced_deps=[dep1]) is not func


def test_async_mismatch(incanter: Incanter) -> None:
    """
    Original function should not be returned if there is a sync/async mismatch.
    """

    def func(x: int) -> int:
        return x + 1

    assert incanter.prepare(func, is_async=True) is not func

    # The other way (adapting an async function into a sync one) is not possible.
