from incant import Incanter
from pytest import fixture


@fixture
def incanter() -> Incanter:
    return Incanter()
