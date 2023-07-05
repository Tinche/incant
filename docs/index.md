# Welcome to incant!

```{toctree}
:maxdepth: 1
:caption: "Contents:"
:hidden:

self
tutorial.md
usage.md
changelog.md
indices.md
modules.rst
```

**incant** is a Python open source library for composing and invoking functions.
Going by the old, humorous adage that dependency injection is simply passing arguments to functions, _incant_ is a toolkit that is well suited to that use case.

_incant_ includes support for:

- matching dependencies by anything in `inspect.Parameter`, including the parameter name, type annotation and default value
- convenient APIs for matching by parameter name and type annotation
- sync and async functions and dependencies
- sync and async context manager dependencies
- no global state
- attaching arbitrary external dependencies to functions (`forced dependencies`), commonly used for side-effects

_incant_ has a very lean API surface, the core API being:

- a single class, `incant.Incanter`, for keeping state (dependency rules)
- a method for registering dependencies: `Incanter.register_hook()`, and a number of higher level, more user-friendly aliases
- methods for invoking arbitrary functions while injecting dependencies: `Incanter.invoke()` and its async variant, `Incanter.ainvoke()`
- methods for invoking arbitrary functions while picking and forwarding any required arguments: `Incanter.incant` and its async variant, `Incanter.aincant`

_incant_ is able to leverage runtime type annotations, but is also capable of functioning without them.
_incant_ is also fully type-annotated for use with Mypy and smart editors.

The tutorial section below contains a walkthough and some real-life use cases of _incant_.

An easy way to remember the difference between `invoke` and `incant` - `incant` is more magical, like a magical incantation.

If you're coming from a _pytest_ background, _incant_ dependency factories are roughly equivalent to _pytest_ fixtures.

# Installation

To install _incant_, simply:

```bash
$ pip install incant
```
