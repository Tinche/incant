from pytest import fixture

from incant import Incanter


@fixture
def incanter() -> Incanter:
    return Incanter()
