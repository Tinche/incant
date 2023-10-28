# incant🪄: a little magic for your functions

[![PyPI](https://img.shields.io/pypi/v/incant.svg)](https://pypi.python.org/pypi/incant)
[![Build](https://github.com/Tinche/incant/workflows/CI/badge.svg)](https://github.com/Tinche/incant/actions?workflow=CI)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Tinche/31981273f39dab936f0000563a30ce3f/raw/covbadge.json)](https://github.com/Tinche/incant/actions/workflows/main.yml)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/incant.svg)](https://github.com/Tinche/incant)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

**incant** is a Python open source library for composing and calling functions.
Going by the old, humorous adage that dependency injection is simply passing arguments to functions, _incant_ is a toolkit that is well suited to that use case.

_incant_ will help you with:

- all kinds of dependency injection scenarios
- adapting interfaces of third-party libraries to make them more flexible
- generically wrapping functions and coroutines for instrumentation
- creating signature-altering decorators
- calling functions and coroutines with unknown signatures safely
- ... and much more!

For example:

```python
from incant import Incanter

incanter = Incanter()

@incanter.register_by_name
def now() -> float:
    """
    Return the current timestamp.

    We can replace this for testing later.
    """
    from time import time

    return time()

def my_function(now: float) -> None:
    print(f"The time now is {now}")

incanter.compose_and_call(my_function)
```

_incant_ has a fully type-annotated interface for use with Mypy and Pyright.
_incant_ works by generating Python code at runtime, and is extremely efficient.
(_incant_ is the fastest Python dependency injection framework we're aware of.)

If you're familiar with _pytest_, _incant_ dependency factories are roughly equivalent to _pytest_ fixtures.

## Project Information

- [**PyPI**](https://pypi.org/project/incant/)
- [**Source Code**](https://github.com/Tinche/incant)
- [**Documentation**](https://incant.threeofwands.com)
- [**Changelog**](https://github.com/Tinche/incant/blob/main/CHANGELOG.md)

## License

_incant_ is written by [Tin Tvrtković](https://threeofwands.com/) and distributed under the terms of the [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) license.
