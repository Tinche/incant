incant🪄: a little magic for your functions
===========================================

.. image:: https://img.shields.io/pypi/v/incant.svg
        :target: https://pypi.python.org/pypi/incant

.. image:: https://github.com/Tinche/incant/workflows/CI/badge.svg
        :target: https://github.com/Tinche/incant/actions?workflow=CI

.. image:: https://codecov.io/gh/Tinche/incant/branch/main/graph/badge.svg?token=9IE6FHZV2K
       :target: https://codecov.io/gh/Tinche/incant

.. image:: https://img.shields.io/pypi/pyversions/incant.svg
        :target: https://github.com/Tinche/incant
        :alt: Supported Python versions

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

----

**incant** is a Python open source library for composing and invoking functions.
Going by the old, humorous adage that dependency injection is simply passing arguments to functions, `incant` is a toolkit that is well suited to that use case.

`incant` includes support for:

* matching dependencies by anything in ``inspect.Parameter``, including the parameter name, type annotation and default value
* convenient APIs for matching by parameter name and type annotation
* sync and async functions and dependencies
* sync and async context manager dependencies
* no global state
* attaching arbitrary external dependencies to functions (``forced dependencies``), commonly used for side-effects

`incant` has a very lean API surface, the core API being:

* a single class, ``incant.Incanter``, for keeping state (dependency rules)
* a method for registering dependencies: ``Incanter.register_hook()``, and a number of higher level, more user-friendly aliases
* methods for invoking arbitrary functions while injecting dependencies: ``Incanter.invoke()`` and its async variant, ``Incanter.ainvoke()``
* methods for invoking arbitrary functions while picking and forwarding any required arguments: ``Incanter.incant`` and its async variant, ``Incanter.aincant``

`incant` is able to leverage runtime type annotations, but is also capable of functioning without them.
`incant` is also fully type-annotated for use with Mypy and smart editors.

The tutorial section below contains a walkthough and some real-life use cases of `incant`.

An easy way to remember the difference between ``invoke`` and ``incant`` - ``incant`` is more magical, like a magical incantation.

If you're coming from a `pytest` background, `incant` dependency factories are roughly equivalent to `pytest` fixtures.

Installation
------------

To install `incant`, simply:

.. code-block:: bash

    $ pip install incant

Tutorial
--------

This section contains a long, narrative-style guide to `incant`.
There is a *Usage* section below with a more focused description of the library API.

Let's demonstrate the use of `incant` with a number of hypothetical scenarios.
While working for a tech company, you've been given an assignment: create a powerful, easy-to-use (yes, both) web framework for other developers in your company to use.
You don't have to do it from scratch though, so you choose (essentially at random) an existing framework: Quart (Quart is an async version of Flask).
Pretty much any other framework (sync or async) would have also worked; other implementations are left as an exercise to the reader.
You decide to call this framework `QuickAPI`.

Simple Quart handlers are very easy to write, so your colleagues are quick to get started:

.. code-block:: python

    from quart import App

    app = App(__name__)

    @app.get("/")
    async def index():
        return "OK"

Simple Dependencies
~~~~~~~~~~~~~~~~~~~

After a while, your colleague says they require the IP address of the incoming request.
You explain the Quart API for this (``request.remote_addr``), but your colleague is adamant about following best practices (avoiding global variables) - they want it as an argument to their handler.
They also want it as an instance of Python's ``ipaddress.IPv4Address``. Their handler looks like this:

.. code-block:: python

    @app.get("/ip")
    async def ip_address_handler(source_ip: IPv4Address) -> str:
        return f"Your address is {source_ip}"

Well, looks like you've got your work cut out for you.

At the top of the file, you import and prepare an ``incant.Incanter`` instance.

.. code-block:: python

    from incant import Incanter

    incanter = Incanter()

You decide to write a function to get the address from the request, and to register it with your Incanter to be matched by type.

.. code-block:: python

    from ipaddress import IPv4Address
    from quart import request

    @incanter.register_by_type
    def get_ip_address() -> IPv4Address:
        # In Quart (like in Flask), the request is accessed through a global proxy
        return IPv4Address(request.remote_addr)

This means any function invoked through the `Incanter` will have any parameters annotated as ``IPv4Address`` satisfied by calling the ``get_ip_address`` dependency factory.

You contemplate how to get this information to the ``ip_address_handler``, and choose to write a simple decorator (yay Python!).
Your colleague agrees, but (citing consistency) wants the decorator to be applied to all handlers going forward.

(You could solve this more elegantly by subclassing the ``quart.Quart`` class but forgo this as this is an `incant` tutorial, not a Quart one.)

You rub your hands and mutter "Let's roll" to yourself.

.. code-block:: python

    from functools import wraps

    def quickapi(handler):
        @wraps(handler)
        async def wrapper():
            return await incanter.ainvoke(handler)

        return wrapper

``incanter.ainvoke`` (the async version of ``invoke``) does what you want - invokes the coroutine you give it while satisfying its arguments from its internal dependency factories.

Then you just apply the decorators to both existing handlers.

.. code-block:: python

    @app.get("/ip")
    @quickapi
    async def ip_address_handler(source_ip: IPv4Address) -> str:
        return f"Your address is {source_ip}"

Passing in Dependencies from the Outside
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some time later, another colleague approaches you asking for path variables to be provided to their handler.
Their handler needs to look like this:

.. code-block:: python

    @app.get("/even-or-odd/<int:integer>")
    @quickapi
    async def even_or_odd_handler(integer: int) -> str:
        return "odd" if integer % 2 != 0 else "even"

Quart provides path parameters like this to handlers as ``kwargs``, so you modify the ``quickapi`` decorator a little:

.. code-block:: python

    def quickapi(handler):
        @wraps(handler)
        async def wrapper(**kwargs):
            return await incanter.ainvoke(handler, **kwargs)

        return wrapper

The decorator simply receives them and passes them along to the handler.
This works because `incant` will use arguments provided to `invoke` if it cannot satisfy a parameter using its internal dependency factories.

Another day of earning your keep!

The Magic of ``incant``
~~~~~~~~~~~~~~~~~~~~~~~

Some time later, another colleague approaches you asking for a logger to be provided to their handler.
They want to use structured logging, and they want the logger to already be bound with the name of the handler.
You think the proposal is well-thought-out and want to use the logger yourself to log every request.

Here's what they want their handler to look like:

.. code-block:: python

    @app.get("/log")
    @quickapi
    async def logging_handler(log: BoundLogger) -> str:
        log.info("Hello from the log handler")
        return "Response after logging"

You reach for the trusty `structlog` library and set it up.

.. code-block:: python

    from structlog.stdlib import BoundLogger, get_logger

    logger = get_logger()  # Useful to have a module-scoped one first.

You change the ``quickapi`` decorator to create and use a logger with the current handler name:

.. code-block:: python

    def quickapi(handler):
        log = logger.bind(handler=handler.__name__)

        @wraps(handler)
        async def wrapper(**kwargs):
            log.info("Processing")
            return await incanter.ainvoke(handler, **kwargs)

        return wrapper

You can't make the logger a dependency within the ``Incanter`` though, since it depends on handler-specific data.
(You could have a separate incanter for each handler, but that's inefficient.)

If the incanter cannot find a dependency to fulfil a parameter, you need to provide it yourself - just like with the path parameters.
Since the ``index`` and ``ip_address_handler`` don't require the logger, we can keep invoking them as before.
However, the ``logging_handler`` handler requires it. Without changes, invoking the handler will let you know:

.. code-block:: python

    TypeError: invoke_logging_handler() missing 1 required positional argument: 'log'

You change the ``quickapi`` decorator to use ``Incanter.aincant`` (the async version of ``Incanter.incant``) and always pass in the logger instance.
``incant`` is meant for cases like this, forwarding the parameters if they are needed and skipping them otherwise.
Since ``incant`` doesn't itself call ``invoke``, you prepare it yourself beforehand.

.. code-block:: python

    def quickapi(handler):
        log = logger.bind(handler=handler.__name__)

        prepared = incanter.prepare(handler)

        @wraps(handler)
        async def wrapper(**kwargs):
            log.info("Processing")
            return await incanter.aincant(prepared, log=log, **kwargs)

        return wrapper

Since you're passing in the logger using ``kwargs``, it will match (after trying name+type) any parameter named ``log``.

Nested Dependencies
~~~~~~~~~~~~~~~~~~~

A colleague is working on an authentication system for your product.
They have a function that takes a cookie (named ``session_token``) and produces an instance of your user model.

.. code-block:: python

    from attrs import define

    @define
    class User:
        """The user model."""
        username: str

    async def current_user(session_token: str) -> User:
        # Complex black magic goes here, immune to timing attacks.
        return User("admin")

They want to be able to use this user model in their handler.

.. code-block:: python

    @app.get("/user")
    @quickapi
    async def user_handler(user: User, log) -> str:
        log.info("Chilling here", user=repr(user))
        return "After the user handler"

You can use their ``current_user`` coroutine directly as a dependency factory:

.. code-block:: python

    incanter.register_by_type(current_user)

but this still leaves the issue of getting the cookie from somewhere.
You define a dependency factory for the session token cookie:

.. code-block:: python

    # We're using a lambda, so we pass in the `name` explicitly.
    incanter.register_by_name(lambda: request.cookies['session_token'], name="session_token")

Because of how ``request.cookies`` works on Quart, this handler will respond with ``400`` if the cookie is not present, or run the handler otherwise.
But only for the handlers that require the ``User`` dependency.

Pretty cool!

Async Context Managers
~~~~~~~~~~~~~~~~~~~~~~

A colleague of yours has heard of this newfangled concept of structured concurrency, and insists on trying it out.
You offer to let them use TaskGroups from the ``quattro`` library.

Their handler looks like this:

.. code-block:: python

    from quattro import TaskGroup

    @app.get("/taskgroup")
    @quickapi
    async def taskgroup_handler(tg: TaskGroup, log: BoundLogger) -> str:
        async def inner():
            log.info("Using structured concurrency, not leaking tasks")

        tg.create_task(inner())
        return "nice"

You don't feel particularly challenged, as ``incant`` support async context managers out of the box and the only thing you need to do is:

.. code-block:: python

    incanter.register_by_type(TaskGroup, is_context_manager="async")

Forced Dependencies
~~~~~~~~~~~~~~~~~~~

Yesterday you've had an outage due to being featured by an influencer on a popular social media site!
You decide to start working on making your services more robust.
Your plan is to apply a limit to how long your service will process each request.
The timeout should default to one second, or it can be provided from the calling service via a header.

You decide to again use the `quattro` library; it has a useful ``fail_after`` context manager that should do the trick.

Since `incant` supports context managers as dependencies, your path is clear:

.. code-block:: python

    from quattro import fail_after

    def apply_timeout(timeout: Header = Header("1.0")) -> ContextManager[CancelScope]:
        return fail_after(float(timeout))

However, our usual approach would require refactoring all our handlers to require this dependency.
Instead, we will make this a *forced dependency*, which means ``incant`` will run it for all handlers.
Since no handler needs the return value of any forced dependency (since they are unaware of them), they are mostly used for side-effects.
We change the ``quickapi`` decorator thusly:

.. code-block:: python

    def quickapi(handler):
        log = logger.bind(handler=handler.__name__)

        prepared = incanter.prepare(handler, forced_deps=[(apply_timeout, "sync")])

        @wraps(handler)
        async def wrapper(**kwargs):
            log.info("Processing")
            return await incanter.aincant(prepared, log=log, **kwargs)

        return wrapper

.. NOTE::
    Since it's not possible to accurately autodetect whether a forced dependency is or isn't a context manager,
    if it *is* a context manager you have to be explicit about it and supply a tuple like in the example.

Complex Rules
~~~~~~~~~~~~~

Another day, another feature request.

A colleague wants to receive instances of `attrs` classes, deserialized from JSON in the request body.
An example:

.. code-block:: python

    @define
    class SamplePayload:
        field: int

    @app.post("/payload")
    @quickapi
    async def attrs_handler(payload: SamplePayload, log) -> str:
        log.info("Received payload", payload=repr(payload))
        return "After payload"

They want this to work for *any* `attrs` class.
You know you can reach for the `cattrs` library to load an attrs class from JSON, but the dependency hook is a little more complex.
Because the dependency hook needs to work for *any* `attrs` class, you need to use ``incanter.register_hook_factory``, the most powerful but lowest level hook registration method.

``incanter.register_hook_factory`` is for, like the name says, factories of dependency hooks.
It will produce a different dependency hook for each `attrs` class we encounter, which is what we need.

.. code-block:: python

    from attrs import has
    from cattrs import structure
    from werkzeug.exceptions import BadRequest

    def make_attrs_payload_factory(attrs_cls: type):
        async def attrs_payload_factory():
            json = await request.get_json(force=True)
            try:
                return structure(json, attrs_cls)
            except Exception as e:
                raise BadRequest() from e

        return attrs_payload_factory


    incanter.register_hook_factory(
        lambda p: has(p.annotation), lambda p: make_attrs_payload_factory(p.annotation)
    )

This will also return a ``400`` status code if the payload cannot be properly loaded.

Because of how `incant` evaluates dependency rules (newest first), this hook factory needs to be registered before the ``current_user`` dependency factory.
Otherwise, since our ``User`` model is also an `attrs` class, `incant` would try loading it from the request body instead of getting it from the ``current_user`` dependency factory.

Complex Rules Pt 2: Electric Boogaloo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A colleague wants to receive HTTP headers in their handler.
They also want these parameters to be able to have default values.
You decide to create a simple string subclass called ``Header`` and have your colleague annotate their parameters with it.
Their header looks like this:

.. code-block:: python

    from typing import NewType

    Header = NewType("Header", str)

    @app.get("/header")
    @quickapi
    async def a_header_handler(content_type: Header = Header("none"), log=logger) -> str:
        return f"The header was: {content_type}"

Since each header parameter needs separate logic, you once again reach for hook factories.
You remember kebab-case is more commonly used than snake_case for headers, so you apply a small transformation - a parameter named ``content_type`` will get the value of the ``content-type`` header field.

You write the necessary instructions:

.. code-block:: python

    def make_header_factory(name: str, default):
        if default is Parameter.empty:
            return lambda: request.headers[name.replace("_", "-")]
        else:
            return lambda: request.headers.get(name.replace("_", "-"), default)

    incanter.register_hook_factory(
        lambda p: p.annotation is Header, lambda p: make_header_factory(p.name, p.default)
    )

The complete source code of this mini-project can be found at https://github.com/Tinche/incant/blob/main/tests/quickapi.py.

Usage
-----

This section contains a quick usage guide to `incant`.

State (in the form of dependency factories) is kept in an instance of ``incant.Incanter``.

.. code-block:: python

    from incant import Incanter

    incanter = Incanter()

The ``incanter`` can now be used to call functions (``invoke``) and coroutines (``ainvoke``).
Since there are no dependency factories registered yet, ``incanter.invoke(fn, a, b, c)`` is equivalent to ``fn(a, b, c)``.

.. code-block:: python

    def my_function(my_argument):
        print(f"Called with {my_argument}")

    incanter.invoke(my_function, 1)
    'Called with 1'

The simplest way to register a dependency factory is by name:

.. code-block:: python

    @incanter.register_by_name
    def my_argument():
        return 2

The result of this dependency factory will be substituted when we invoke a function that has an argument named ``my_argument``.

.. code-block:: python

    incanter.invoke(my_function)
    'Called with 2'

Another simple way to register a dependency factory is by its return type:

.. code-block:: python

    @incanter.register_by_type
    def another_factory(my_argument) -> int:
        return my_argument + 1

    def another_function(takes_int: int):
        print(f"Called with {takes_int}")

    incanter.invoke(another_function)
    'Called with 3'

Dependency factories may themselves have dependencies provided to them, as shown in the above example.
``incant`` performs a depth-first pass of gathering nested dependencies.

``incanter.invoke`` uses ``incanter.prepare`` internally.
``prepare`` does the actual heavy lifting of creating and caching a wrapper with the dependencies processed and wired.
It's useful for getting the wrappers for caching or inspection - the wrappers support ordinary Python introspection using the standard library `inspect` module.

``prepare`` also allows customizing the wrapper without adding hooks to the actual ``Incanter``.

.. code-block:: python

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

The hook argument is a sequence of hooks, which are a predicate function and dependency factory.
Also be aware that since in Python lambdas don't play well with caching, if you're preparing functions with hook overrides often you will want to store the actual overrides somewhere and reuse them.

.. code-block:: python

    # Inefficient:
    >>> incanter.prepare(lambda: my_argument, [Hook.for_name("my_argument", lambda: 1)])()

    # Efficient:
    >>> additional_hooks = [Hook.for_name("my_argument", lambda: 1)] # Store this and reuse it.

    >>> incanter.prepare(lambda: my_argument, additional_hooks)()  # Now uses the cache.

Incanter instances also have a helper method, ``incanter.incant`` (and ``incanter.aincant``), that serves as a smart helper for calling functions.
``incanter.incant`` filters out unnecessary arguments before calling the given function, and is a useful tool for building generic components.
``incanter.incant`` also composes nicely with ``prepare``, where you can prepare a function in advance (to inject dependencies) and incant it with proper parameters.

``register_by_name`` and ``register_by_type`` delegate to ``incanter.register_hook``.
``register_hook`` takes a predicate function and a dependency factory.
When determining if a depency factory can be used for a parameter, ``incant`` will try predicate functions (from newest to oldest) until one matches and use that dependency.
Predicate functions take an ``inspect.Parameter`` and return a ``bool``, so they can match using anything present in ``Parameter``.

``register_hook`` delegates to ``register_hook_factory``, which takes a predicate function and a factory of depedendency factories.
This outer factory takes an ``inspect.Parameter`` and returns a depedency factory, enabling generic depedendency factories.

Changelog
---------
22.2.2 (2022-12-31)
~~~~~~~~~~~~~~~~~~~
* Fix an optimization for explicitly sync functions.
* Fix an issue incanting unnecessary positional arguments.
* Support ``__future__`` annotations (PEP 563) on Python 3.10+.

22.2.1 (2022-12-27)
~~~~~~~~~~~~~~~~~~~
* Fix an issue when wrapping a sync function with an async one.

22.2.0 (2022-12-26)
~~~~~~~~~~~~~~~~~~~
* Python 3.11 support.
* Fix ``unbound local error`` while generating code.
  (`#4 <https://github.com/Tinche/incant/issues/4>`_)
* Avoid using local variables in generated code when possible.
* When ``incant.prepare`` cannot do anything for a function, return the original function for efficiency.

22.1.0 (2022-09-02)
~~~~~~~~~~~~~~~~~~~
* *Breaking change*: due to limitations in autodetecting context managers (both sync and async), context manager dependencies must be explicitly registered by passing ``is_context_manager="sync"`` (or ``async``) to the registration functions.
* Injection can be customized on a per-parameter basis by annotating a parameter with ``Annotated[type, incant.Override(...)]``.
* Implement support for forced dependencies.
* Sync context managers may now be dependencies.
* ``incanter.a/incant()`` now handles unfulfilled parameters with defaults properly.
* Switched to CalVer.

0.3.0 (2022-02-03)
~~~~~~~~~~~~~~~~~~
* Properly set the return type annotation when preparing a function.
* A hook override can now force a dependency to be promoted to a parameter (instead of being satisfied) by setting ``Hook.factory`` to ``None``.
* Parameters with defaults are now supported for ``incanter.prepare`` and ``incanter.a/invoke``.
* ``incanter.a/incant`` no longer uses ``invoke`` under the hood, to allow greater customization. Previous behavior can be replicated by ``incant(prepare(fn))``.
* Optional arguments of dependencies can now be propagated to final function arguments. Keyword-only arguments of dependencies are still filtered out.

0.2.0 (2022-01-13)
~~~~~~~~~~~~~~~~~~
* Introduce ``incanter.prepare``, and make ``incanter.a/invoke`` use it. ``prepare`` just generates the prepared injection wrapper for a function and returns it, without executing it.
* Remove ``incanter.parameters``, since it's now equivalent to ``inspect.signature(incanter.prepare(fn)).parameters``.
* Add the ability to pass hook overrides to ``incanter.prepare``, and introduce the ``incanter.Hook`` class to make it more usable.

0.1.0 (2022-01-10)
~~~~~~~~~~~~~~~~~~
* Initial release.
