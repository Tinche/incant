```{currentmodule} incant

```

# Tutorial

This section contains a long, narrative-style guide to _incant_.
See the [Usage section](usage.md) with a more focused description of the library API.

Let's demonstrate the use of _incant_ with a number of hypothetical scenarios.
While working for a tech company, you've been given an assignment: create a powerful, easy-to-use (yes, both) web framework for other developers in your company to use.
You don't have to do it from scratch though, so you choose (essentially at random) an existing framework - [Quart](http://pgjones.gitlab.io/quart/) (Quart is an async version of Flask).
Pretty much any other framework (sync or async) would have also worked; other implementations are left as an exercise to the reader.
You decide to call this framework `QuickAPI`.

Simple Quart handlers are very easy to write, so your colleagues are quick to get started:

```python
from quart import App

app = App(__name__)

@app.get("/")
async def index():
    return "OK"
```

## Simple Dependencies

After a while, your colleague says they require the IP address of the incoming request.
You explain the Quart API for this (`request.remote_addr`), but your colleague is adamant about following best practices (avoiding global variables) - they want it as an argument to their handler.
They also want it as an instance of Python's [`ipaddress.IPv4Address`](https://docs.python.org/3/library/ipaddress.html#ipaddress.IPv4Address).
Their handler looks like this:

```python
@app.get("/ip")
async def ip_address_handler(source_ip: IPv4Address) -> str:
    return f"Your address is {source_ip}"
```

At the top of the file, you import and prepare an {class}`Incanter` instance.

```python
from incant import Incanter

incanter = Incanter()
```

You decide to write a function to get the address from the request, and to register it with your Incanter to be matched by type.

```python
from ipaddress import IPv4Address
from quart import request

@incanter.register_by_type
def get_ip_address() -> IPv4Address:
    # In Quart (like in Flask), the request is accessed through a global proxy
    return IPv4Address(request.remote_addr)
```

This means any function invoked through the `Incanter` will have any parameters annotated as `IPv4Address` satisfied by calling the `get_ip_address` dependency factory.

You contemplate how to get this information to the `ip_address_handler`, and choose to write a simple decorator (yay Python!).
Your colleague agrees, but (citing consistency) wants the decorator to be applied to all handlers going forward.

(You could solve this particular problem by subclassing the `quart.Quart` class but forgo this as this is an _incant_ tutorial, not a Quart one.)

You rub your hands and mutter "Let's roll" to yourself.

```python
from functools import wraps

def quickapi(handler):
    @wraps(handler)
    async def wrapper():
        return await incanter.acompose_and_call(handler)

    return wrapper
```

{meth}`Incanter.ainvoke` (the async version of {meth}`Incanter.invoke`) does what you want - invokes the coroutine you give it while satisfying its arguments from its internal dependency factories.

Then you just apply the decorators to both existing handlers.

```python
@app.get("/ip")
@quickapi
async def ip_address_handler(source_ip: IPv4Address) -> str:
    return f"Your address is {source_ip}"
```

## Passing in Dependencies from the Outside

Some time later, another colleague approaches you asking for path variables to be provided to their handler.
Their handler needs to look like this:

```python
@app.get("/even-or-odd/<int:integer>")
@quickapi
async def even_or_odd_handler(integer: int) -> str:
    return "odd" if integer % 2 != 0 else "even"
```

Quart provides path parameters like this to handlers as `kwargs`, so you modify the `quickapi` decorator a little:

```python
def quickapi(handler):
    @wraps(handler)
    async def wrapper(**kwargs):
        return await incanter.acompose_and_call(handler, **kwargs)

    return wrapper
```

The decorator simply receives them and passes them along to the handler.
This works because _incant_ will use arguments provided to {meth}`~Incanter.compose_and_call` if it cannot satisfy a parameter using its internal dependency factories.

Another day of earning your keep!

## The Magic of _incant_

Some time later, another colleague approaches you asking for a logger to be provided to their handler.
They want to use structured logging, and they want the logger to already be bound with the name of the handler.
You think the proposal is well-thought-out and want to use the logger yourself to log every request.

Here's what they want their handler to look like:

```python
@app.get("/log")
@quickapi
async def logging_handler(log: BoundLogger) -> str:
    log.info("Hello from the log handler")
    return "Response after logging"
```

You reach for the trusty [_structlog_](https://structlog.org) library and set it up.

```python
from structlog.stdlib import BoundLogger, get_logger

logger = get_logger()  # Useful to have a module-scoped one first.
```

You change the `quickapi` decorator to create and use a logger with the current handler name:

```python
def quickapi(handler):
    log = logger.bind(handler=handler.__name__)

    @wraps(handler)
    async def wrapper(**kwargs):
        log.info("Processing")
        return await incanter.acompose_and_call(handler, **kwargs)

    return wrapper
```

You can't make the logger a dependency within the `Incanter` though, since it depends on handler-specific data.
(You could have a separate incanter for each handler, but that's inefficient.)

If the incanter cannot find a dependency to fulfil a parameter, you need to provide it yourself - just like with the path parameters.
Since the `index` and `ip_address_handler` don't require the logger, we can keep invoking them as before.
However, the `logging_handler` handler requires it. Without changes, invoking the handler will let you know:

```python
TypeError: invoke_logging_handler() missing 1 required positional argument: 'log'
```

You change the `quickapi` decorator to use {meth}`Incanter.aincant` (the async version of {meth}`Incanter.incant`) and always pass in the logger instance.
_incant_ is meant for cases like this, forwarding the parameters if they are needed and skipping them otherwise.
Since _incant_ doesn't itself call `compose_and_call`, you prepare it yourself beforehand.

```python
def quickapi(handler):
    log = logger.bind(handler=handler.__name__)

    prepared = incanter.compose(handler)

    @wraps(handler)
    async def wrapper(**kwargs):
        log.info("Processing")
        return await incanter.aincant(prepared, log=log, **kwargs)

    return wrapper
```

Since you're passing in the logger using `kwargs`, it will match (after trying name+type) any parameter named `log`.

## Nested Dependencies

A colleague is working on an authentication system for your product.
They have a function that takes a cookie (named `session_token`) and produces an instance of your user model.

```python
from attrs import define

@define
class User:
    """The user model."""
    username: str

async def current_user(session_token: str) -> User:
    # Complex black magic goes here, immune to timing attacks and whatnot.
    return User("admin")
```

They want to be able to use this user model in their handler.

```python
@app.get("/user")
@quickapi
async def user_handler(user: User, log) -> str:
    log.info("Chilling here", user=repr(user))
    return "After the user handler"
```

You can use their `current_user` coroutine directly as a dependency factory:

```python
incanter.register_by_type(current_user)
```

but this still leaves the issue of getting the session token from somewhere.
You define a dependency factory for the session token cookie, using a lambda this time:

```python
# We're using a lambda, so we pass in the `name` explicitly.
incanter.register_by_name(lambda: request.cookies['session_token'], name="session_token")
```

Because of how `request.cookies` works on Quart, this handler will respond with `400` if the cookie is not present, or run the handler otherwise.
But only for the handlers that require the `User` dependency.

Pretty cool!

## Async Context Managers

A colleague of yours has heard of this newfangled concept of structured concurrency, and insists on trying it out.
You offer to let them use TaskGroups from the [_quattro_](https://github.com/Tinche/quattro/) library.

Their handler looks like this:

```python
from quattro import TaskGroup

@app.get("/taskgroup")
@quickapi
async def taskgroup_handler(tg: TaskGroup, log: BoundLogger) -> str:
    async def inner():
        log.info("Using structured concurrency, not leaking tasks")

    tg.create_task(inner())
    return "nice"
```

You don't feel particularly challenged, as _incant_ supports async context managers out of the box and the only thing you need to do is:

```python
incanter.register_by_type(TaskGroup, is_context_manager="async")
```

## Forced Dependencies

Yesterday you've had an outage due to being featured by an influencer on a popular social media site!
You decide to start working on making your services more robust.
Your plan is to apply a limit to how long your service will process each request.
The timeout should default to one second, or it can be provided from the calling service via a header.

You decide to again use the _quattro_ library; it has a useful `fail_after` context manager that should do the trick.

Since _incant_ supports context managers as dependencies, your path is clear:

```python
from quattro import fail_after

def apply_timeout(timeout: Header = Header("1.0")) -> ContextManager[CancelScope]:
    return fail_after(float(timeout))
```

However, our usual approach would require refactoring all our handlers to require this dependency.
Instead, we will make this a _forced dependency_, which means _incant_ will run it for all handlers.
Since no handler needs the return value of any forced dependency (since they are unaware of them), they are mostly used for side-effects.
We change the `quickapi` decorator thusly:

```python
def quickapi(handler):
    log = logger.bind(handler=handler.__name__)

    prepared = incanter.compose(handler, forced_deps=[(apply_timeout, "sync")])

    @wraps(handler)
    async def wrapper(**kwargs):
        log.info("Processing")
        return await incanter.aincant(prepared, log=log, **kwargs)

    return wrapper
```

Since it's not possible to accurately autodetect whether a forced dependency is or isn't a context manager,
if it _is_ a context manager you have to be explicit about it and supply a tuple like in the example.

## Complex Rules

Another day, another feature request.

A colleague wants to receive instances of _attrs_ classes, deserialized from JSON in the request body.
An example:

```python
@define
class SamplePayload:
    field: int

@app.post("/payload")
@quickapi
async def attrs_handler(payload: SamplePayload, log) -> str:
    log.info("Received payload", payload=repr(payload))
    return "After payload"
```

They want this to work for _any_ _attrs_ class.
You know you can reach for the _cattrs_ library to load an _attrs_ class from JSON, but the dependency hook is a little more complex.
Because the dependency hook needs to work for _any_ _attrs_ class, you need to use {meth}`Incanter.register_hook_factory`, the most powerful but lowest level hook registration method.

`register_hook_factory()` is for, like the name says, factories of dependency hooks.
It will produce a different dependency hook for each _attrs_ class we encounter, which is what we need.

```python
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
```

This will also return a `400` status code if the payload cannot be properly loaded.

Because of how _incant_ evaluates dependency rules (newest first), this hook factory needs to be registered before the `current_user` dependency factory.
Otherwise, since our `User` model is also an _attrs_ class, _incant_ would try loading it from the request body instead of getting it from the `current_user` dependency factory.

## Complex Rules Pt 2: Electric Boogaloo

A colleague wants to receive HTTP headers in their handler.
They also want these parameters to be able to have default values.
You decide to create a simple string subclass called `Header` and have your colleague annotate their parameters with it.
Their header looks like this:

```python
from typing import NewType

Header = NewType("Header", str)

@app.get("/header")
@quickapi
async def a_header_handler(content_type: Header = Header("none"), log=logger) -> str:
    return f"The header was: {content_type}"
```

Since each header parameter needs separate logic, you once again reach for hook factories.
You remember kebab-case is more commonly used than snake_case for headers, so you apply a small transformation - a parameter named `content_type` will get the value of the `content-type` header field.

You write the necessary instructions:

```python
def make_header_factory(name: str, default):
    if default is Parameter.empty:
        return lambda: request.headers[name.replace("_", "-")]
    else:
        return lambda: request.headers.get(name.replace("_", "-"), default)

incanter.register_hook_factory(
    lambda p: p.annotation is Header, lambda p: make_header_factory(p.name, p.default)
)
```

The complete source code of this mini-project can be found at [quickapi.py](https://github.com/Tinche/incant/blob/main/tests/quickapi.py).
