"""
Benchmark module for the `single_dep` scenario.

A function with a single dependency; the dependency is satisfied by the container and produces integers.
"""
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
from di import Container, Dependant
from wired import ServiceRegistry

from incant import Incanter


def dep1():
    return 2


def func(dep1: int):
    return dep1 + 1


incant = Incanter()
incant.register_by_name(dep1)


def incant_call_func():
    incant.invoke(func)


# wired

service_registry = ServiceRegistry()
service_registry.register_singleton(lambda: func(dep1()), name="func")


def wired_call_func():
    container = service_registry.create_container()
    func = container.get(name="func")
    func()


# di

container = Container()
container.bind(dep1, int)


def di_call_func():
    container.execute_sync(container.solve(Dependant(func)))


# Dependency-injector
class DepInjContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    dep1 = providers.Callable(dep1)


@inject
def dep_inj_func(dep1: int = Provide[DepInjContainer.dep1]):
    return dep1 + 1


dep_inj_container = DepInjContainer()
dep_inj_container.wire(modules=[__name__])


def dependency_injector_call_func():
    dep_inj_func()
