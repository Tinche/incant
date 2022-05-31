from asyncio import sleep
from functools import wraps
from inspect import Parameter
from ipaddress import IPv4Address
from typing import ContextManager, NewType

from attrs import define, has
from cattrs import structure
from quart import Quart, request
from quattro import CancelScope, TaskGroup, fail_after
from structlog.stdlib import BoundLogger, get_logger
from werkzeug.exceptions import BadRequest

from incant import Incanter


app = Quart(__name__)
incanter = Incanter()
logger = get_logger()


Header = NewType("Header", str)


def apply_timeout(timeout: Header = Header("1.0")) -> ContextManager[CancelScope]:
    return fail_after(float(timeout))


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
incanter.register_by_type(TaskGroup, is_ctx_manager="async")


@incanter.register_by_type
def get_ip_address() -> IPv4Address:
    # In Quart (like in Flask), the request is accessed through a global proxy
    return IPv4Address(request.remote_addr)


@define
class User:
    """The user model."""

    username: str


async def current_user(session_token: str) -> User:
    # Complex black magic goes here, immune to timing attacks.
    return User("admin")


incanter.register_by_type(current_user)
incanter.register_by_name(
    lambda: request.cookies["session_token"], name="session_token"
)


def make_header_factory(name: str, default):
    if default is Parameter.empty:
        return lambda: request.headers[name.replace("_", "-")]
    else:
        return lambda: request.headers.get(name.replace("_", "-"), default)


incanter.register_hook_factory(
    lambda p: p.annotation is Header, lambda p: make_header_factory(p.name, p.default)
)


def quickapi(handler):
    log = logger.bind(handler=handler.__name__)

    prepared = incanter.prepare(
        handler, is_async=True, forced_deps=[(apply_timeout, "sync")]
    )

    @wraps(handler)
    async def wrapper(**kwargs):
        log.info("Processing")
        return await incanter.aincant(prepared, log=log, **kwargs)

    return wrapper


@app.get("/")
@quickapi
async def index():
    return "OK"


@app.get("/ip")
@quickapi
async def ip_address_handler(source_ip: IPv4Address) -> str:
    return f"Your address is {source_ip}"


@app.get("/log")
@quickapi
async def logging_handler(log: BoundLogger) -> str:
    log.info("Hello from the log handler")
    return "Response after logging"


@app.get("/even-or-odd/<int:integer>")
@quickapi
async def even_or_odd_handler(integer: int) -> str:
    return "odd" if integer % 2 != 0 else "even"


@app.get("/user")
@quickapi
async def user_handler(user: User, log) -> str:
    log.info("Chilling here", user=repr(user))
    return "After the user handler"


@define
class SamplePayload:
    field: int


@app.post("/payload")
@quickapi
async def attrs_handler(payload: SamplePayload, log: BoundLogger) -> str:
    log.info("Received payload", payload=repr(payload))
    return "After payload"


@app.get("/taskgroup")
@quickapi
async def taskgroup_handler(tg: TaskGroup, log: BoundLogger) -> str:
    async def inner():
        log.info("Using structured concurrency, not leaking tasks")

    tg.create_task(inner())
    return "nice"


@app.get("/header")
@quickapi
async def a_header_handler(content_type: Header = Header("none"), log=logger) -> str:
    return f"The header was: {content_type}"


@app.get("/slow")
@quickapi
async def slow() -> str:
    await sleep(5)
    return "DONE!"


if __name__ == "__main__":
    app.run()
