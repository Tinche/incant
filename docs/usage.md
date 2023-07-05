# Usage

This section contains a quick usage guide to _incant_.

State (in the form of dependency factories) is kept in an instance of {class}`incant.Incanter`.

```python
from incant import Incanter

incanter = Incanter()
```

The `incanter` can now be used to call functions ({meth}`incant.Incanter.invoke`) and coroutines ({meth}`incant.Incanter.ainvoke`).
Since there are no dependency factories registered yet, `incanter.invoke(fn, a, b, c)` is equivalent to `fn(a, b, c)`.

```python
def my_function(my_argument):
    print(f"Called with {my_argument}")

incanter.invoke(my_function, 1)
'Called with 1'
```

The simplest way to register a dependency factory is by name:

```python
@incanter.register_by_name
def my_argument():
    return 2
```

The result of this dependency factory will be substituted when we invoke a function that has an argument named `my_argument`.

```python
incanter.invoke(my_function)
'Called with 2'
```

Another simple way to register a dependency factory is by its return type:

```python
@incanter.register_by_type
def another_factory(my_argument) -> int:
    return my_argument + 1

def another_function(takes_int: int):
    print(f"Called with {takes_int}")

incanter.invoke(another_function)
'Called with 3'
```

Dependency factories may themselves have dependencies provided to them, as shown in the above example.
_incant_ performs a depth-first pass of gathering nested dependencies.

`Incanter.invoke()` uses {meth}`Incanter.prepare() <incant.Incanter.prepare>` internally.
`prepare()` does the actual heavy lifting of creating and caching a wrapper with the dependencies processed and wired.
It's useful for getting the wrappers for caching or inspection - the wrappers support ordinary Python introspection using the standard library [`inspect`](https://docs.python.org/3/library/inspect.html) module.

`prepare()` also allows customizing the wrapper without adding hooks to the actual `Incanter`.

```python
from incant import Hook

@incanter.register_by_name
def my_argument():
    return 2

def my_function(my_argument):
    print(f"Called with {my_argument}")

>>> incanter.invoke(my_function)
2

>>> incanter.prepare(lambda: my_argument)()  # Equivalent.
2

>>> incanter.prepare(lambda: my_argument, [Hook.for_name("my_argument", lambda: 1)])()
1
```

The hook argument is a sequence of hooks, which are a predicate function and dependency factory.
Also be aware that since in Python lambdas don't play well with caching, if you're preparing functions with hook overrides often you will want to store the actual overrides somewhere and reuse them.

```python
# Inefficient:
>>> incanter.prepare(lambda: my_argument, [Hook.for_name("my_argument", lambda: 1)])()

# Efficient:
>>> additional_hooks = [Hook.for_name("my_argument", lambda: 1)] # Store this and reuse it.

>>> incanter.prepare(lambda: my_argument, additional_hooks)()  # Now uses the cache.
```

Incanter instances also have helper methods, {meth}`Incanter.incant() <incant.Incanter.incant>` and {meth}`Incanter.aincant() <incant.Incanter.aincant>` that serve as a smart helper for calling functions.
`Incanter.incant()` filters out unnecessary arguments before calling the given function, and is a useful tool for building generic components.
`Incanter.incant()` also composes nicely with `prepare()`, where you can prepare a function in advance (to inject dependencies) and incant it with proper parameters.

`register_by_name` and `register_by_type` delegate to {meth}`Incanter.register_hook() <incant.Incanter.register_hook>`.
`register_hook()` takes a predicate function and a dependency factory.
When determining if a depency factory can be used for a parameter, _incant_ will try predicate functions (from newest to oldest) until one matches and use that dependency.
Predicate functions take an [`inspect.Parameter`](https://docs.python.org/3/library/inspect.html#inspect.Parameter) and return a `bool`, so they can match using anything present in `Parameter`.

`register_hook()` delegates to {meth}`Incanter.register_hook_factory() <incant.Incanter.register_hook_factory>`, which takes a predicate function and a factory of depedendency factories.
This outer factory takes an `inspect.Parameter` and returns a depedency factory, enabling generic depedendency factories.
