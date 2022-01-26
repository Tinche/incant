from inspect import Parameter, Signature, signature

from incant import Incanter


def test_params_with_defaults():
    """Default values should be propagated properly."""
    incant = Incanter()

    def fn(default_param=1):
        return default_param

    assert incant.invoke(fn) == 1

    assert signature(incant.prepare(fn)) == Signature(
        [Parameter("default_param", Parameter.POSITIONAL_OR_KEYWORD, default=1)]
    )
