incant: a little magic for your functions
=========================================

.. image:: https://img.shields.io/pypi/v/incant.svg
        :target: https://pypi.python.org/pypi/incant

.. image:: https://github.com/Tinche/incant/workflows/CI/badge.svg
        :target: https://github.com/Tinche/incant/actions?workflow=CI

.. image:: https://codecov.io/gh/Tinche/inject/branch/main/graph/badge.svg?token=9IE6FHZV2K
       :target: https://codecov.io/gh/Tinche/inject

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

----

**incant** is an Apache 2 licensed library, written in Python, for composing and invoking functions.
Going by the old, humorous adage that dependency injection is simply passing arguments to functions, `incant` is a toolkit that is well suited to that use case.

`incant` includes support for:
* matching dependencies by anything in `inspect.Parameter`, including the parameter name, type annotation and default value
* convenient APIs for matching by parameter name and type annotation
* sync and async functions and dependencies
* async context manager dependencies
* no global state

`incant` has a very lean API surface, the core API being:
* a single class, ``incant.Incanter``, for keeping state (dependency rules)
* a method for registering dependencies: ``Incanter.register_hook()``, and a number of higher level, more user-friendly aliases
* methods for invoking arbitrary functions while injecting dependencies: ``Incanter.invoke()`` and its async variant, ``Incanter.ainvoke()``
* a method for getting the parameters of an arbitrary function after injecting dependencies: ``Incanter.parameters()``
* methods for invoking arbitrary functions while injecting dependencies and forwarding any required arguments: ``Incanter.incant`` and its async variant, ``Incanter.aincant``

The tutorial section below contains a walkthough and some real-life use cases of `incant`.

An easy way to remember the difference between ``invoke`` and ``incant`` - ``incant`` is more magical, like a magical incantation.

If you're coming from a `pytest` background, `incant` dependency factories are roughly equivalent to `pytest` fixtures.

Installation
------------

To install `incant`, simply:

.. code-block:: bash

    $ pip install incant

Usage
-----

This section contains a quick usage guide to `incant`. The tutorial second below contains a longer, narrative-style walkthough.

Tutorial
--------

Let's demonstrate the use of `incant` with a hypothetical scenario.
While working for a tech company, you've been given an assignment: create a powerful, easy-to-use (yes, both) web framework for other developers in your company to use.
You don't have to do it from scratch though, so you choose (essentially at random) an existing framework: Quart (Quart is an async version of Flask).
Pretty much any other framework (sync or async) would have also worked; other implementations are left as an exercise to the reader.
You decide to call this framework `IncantAPI`.

Simple Quart handlers are very easy to write, so your colleagues are quick to get started:

.. code-block:: python

    @app.get("/")
    async def index():
        return "OK"

Simple Dependencies
~~~~~~~~~~~~~~~~~~~

After a while, your colleague says they require the IP address for the incoming request.
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
Your colleague agrees, but (citing consistency) wants the decorator to be applied to all handlers.

(You could solve this more elegantly by subclassing the ``quart.Quart`` class, but forgo this as this is an `incant` tutorial, not a Quart one.)

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

Some time later, another colleague approaches you asking for a logger to be provided to their handler.
They want to use structured logging, and they want the logger to already be bound with the name of the handler.
You think the proposal is well thought-out, and want to use the logger yourself to log every request.

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
        async def wrapper():
            log.info("Processing")
            return await incanter.ainvoke(handler)

        return wrapper

You can't make the logger a dependency within the ``Incanter`` though, since it depends on handler-specific data.
(You could have a separate incanter for each handler, but that's very inefficient.)

If the incanter cannot find a dependency to fulfil a parameter, you need to provide it yourself.
Since the ``index`` and ``ip_address_handler`` don't require the logger, we can keep invoking them as before.
However, the ``logging_handler`` handler requires it. Without changes, invoking the handler will let you know:

.. code-block:: python

    TypeError: invoke_logging_handler() missing 1 required positional argument: 'log'

You change the ``quickapi`` decorator to use ``Incanter.aincant`` (the async version of ``Incanter.incant``) and always pass in the logger instance.
``incant`` is meant for cases like this, forwarding the parameters if they are needed and skipping them otherwise.

.. code-block:: python

    def quickapi(handler):
        log = logger.bind(handler=handler.__name__)

        @wraps(handler)
        async def wrapper():
            log.info("Processing")
            return await incanter.aincant(handler, log=log)

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
    from cattr import structure
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

Changelog
---------

0.1.0 (UNRELEASED)
~~~~~~~~~~~~~~~~~~
* Initial release.