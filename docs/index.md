# Welcome to incant🪄!

```{toctree}
:maxdepth: 1
:caption: "Contents:"
:hidden:

self
usage.md
tutorial.md
changelog.md
indices.md
modules.rst
```

```{currentmodule} incant

```

**incant** is a Python open source library for **composing** and **calling functions**.
_Dependency injection_ is but one of many use-cases served well by _incant_; wrapping functions with context managers for observability is another.

_incant_ includes support for:

- a convenience layer with a simple API, based on a powerful and fast performance layer
- a very flexible system for matching dependencies using [`inspect.Parameter`](https://docs.python.org/3/library/inspect.html#inspect.Parameter), including the parameter name, type annotation and default value
- sync and async functions and dependencies
- sync and async context manager dependencies
- no global state
- attaching arbitrary external dependencies to functions (_forced dependencies_), commonly used for side-effects

_incant_ has a very lean API surface, the core API being:

- a single class, {class}`incant.Incanter`, for keeping state (dependency rules)
- a method for registering dependencies, {meth}`Incanter.register_hook`, and a number of higher level, more user-friendly helpers ({meth}`Incanter.register_by_name`, {meth}`Incanter.register_by_type`)
- methods for calling arbitrary functions while composing them with their dependencies, {meth}`Incanter.compose_and_call` and its async variant, {meth}`Incanter.acompose_and_call`
- methods for invoking arbitrary functions while picking and forwarding any required arguments, {meth}`Incanter.incant` and its async variant, {meth}`Incanter.aincant`
- methods for composing functions in advance, without calling them, {meth}`Incanter.compose`
- methods for adjusting arbitrary functions to arbitrary parameters, {meth}`Incanter.adapt`

_incant_ is able to leverage runtime type annotations but is also capable of functioning without them.
_incant_ is also fully type-annotated for use with Mypy and smart editors.

The [Tutorial](tutorial.md) contains a walkthough and some real-life use cases of _incant_.

If you're coming from a _pytest_ background, _incant_ dependency factories are roughly equivalent to _pytest_ fixtures.

# Installation

To install _incant_, simply:

```bash
$ pip install incant
```
