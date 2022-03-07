"""
Benchmark module for the `two_deps` scenario.

A function with two dependencies; the first depends on the other, and the other requires a parameter.
"""
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
from di import Container, Dependant, SyncExecutor
from di.container import bind_by_type
from wired import ServiceRegistry

from incant import Incanter


def dep2(input: str) -> float:
    return float(input) + 1


def dep1(dep2: float) -> int:
    return int(dep2) + 1


def func(dep1: int):
    return dep1 + 1


incant = Incanter()
incant.register_by_name(dep1)
incant.register_by_name(dep2)


def incant_call_func():
    incant.prepare(func)("1")


# wired

service_registry = ServiceRegistry()
service_registry.register_factory(
    lambda container: dep2(container.get(name="input")), name="dep2"
)
service_registry.register_factory(
    lambda container: dep1(container.get(name="dep2")), name="dep1"
)
service_registry.register_factory(
    lambda container: func(container.get(name="dep1")), name="func"
)


def wired_call_func():
    container = service_registry.create_container()
    container.register_singleton("1", name="input")
    container.get(name="func")


# di

container = Container()
executor = SyncExecutor()
container.bind(bind_by_type(Dependant(dep1), int))
container.bind(bind_by_type(Dependant(dep2), float))
solved = container.solve(Dependant(func), scopes=(None,))


def di_call_func():
    with container.enter_scope(None) as state:
        container.execute_sync(solved, values={str: "1"}, state=state, executor=executor)


# Dependency-injector
class DepInjContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    func_factory = providers.Factory(
        func, dep1=providers.Factory(dep1, dep2=providers.Factory(dep2))
    )


dep_inj_container = DepInjContainer()
dep_inj_container.wire(modules=[__name__])


def dependency_injector_call_func():
    dep_inj_container.func_factory(dep1__dep2__input="1")
