from functools import wraps
from ipaddress import IPv4Address

from attrs import define, has
from cattr import structure
from quart import Quart, request
from structlog.stdlib import BoundLogger, get_logger
from werkzeug.exceptions import BadRequest

from incant import Incanter


app = Quart(__name__)
incanter = Incanter()
logger = get_logger()


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


def quickapi(handler):
    log = logger.bind(handler=handler.__name__)

    @wraps(handler)
    async def wrapper():
        log.info("Processing")
        return await incanter.aincant(handler, log=log)

    return wrapper


@incanter.register_by_type
def get_ip_address() -> IPv4Address:
    # In Quart (like in Flask), the request is accessed through a global proxy
    return IPv4Address(request.remote_addr)


@app.get("/")
@quickapi
async def index():
    print(request.remote_addr)
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
async def attrs_handler(payload: SamplePayload, log) -> str:
    log.info("Received payload", payload=repr(payload))
    return "After payload"


app.run()
