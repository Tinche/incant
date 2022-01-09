from functools import lru_cache
from inspect import Parameter, Signature, iscoroutinefunction, signature
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from attr import Factory, define, field

from ._codegen import LocalVarFactory, ParameterDep, compile_fn


_type = type


R = TypeVar("R")


@define
class FactoryDep:
    factory: Callable
    arg_name: str


Dep = Union[FactoryDep, ParameterDep]


PredicateFn = Callable[[Parameter], bool]


@define
class Incanter:
    hook_factory_registry: List[Tuple[PredicateFn, Callable]] = Factory(list)
    _invoke_cache: Callable = field(
        init=False,
        default=Factory(lambda self: lru_cache(None)(self._gen_fn), takes_self=True),
    )

    def invoke(self, fn: Callable[..., R], *args, **kwargs) -> R:
        return self._invoke_cache(fn)(*args, **kwargs)

    async def ainvoke(self, fn: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
        return await self._invoke_cache(fn, True)(*args, **kwargs)

    def incant(self, fn: Callable[..., R], *args, **kwargs) -> R:
        """Invoke `fn` the best way we can."""
        return self._incant(fn, args, kwargs)

    async def aincant(self, fn: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
        """Invoke async `fn` the best way we can."""
        return await self._incant(fn, args, kwargs, is_async=True)

    def parameters(self, fn: Callable) -> Mapping[str, Parameter]:
        """Return the signature needed to successfully and exactly invoke `fn`."""
        return signature(self._invoke_cache(fn, is_async=None)).parameters

    def register_by_name(
        self, fn: Optional[Callable] = None, *, name: Optional[str] = None
    ):
        """
        Register a factory to be injected by name. Can also be used as a decorator.

        If the name is not provided, the name of the factory will be used.
        """
        if fn is None:
            # Decorator
            return lambda fn: self.register_by_name(fn, name=name)

        if name is None:
            name = fn.__name__
        self.register_hook(lambda p: p.name == name, fn)

    def register_by_type(self, fn: Optional[Callable], type: Optional[Type] = None):
        """
        Register a factory to be injected by type. Can also be used as a decorator.

        If the type is not provided, the return annotation from the
        factory will be used.
        """
        if type is None:
            if fn.__class__ is _type:
                type = fn
            else:
                sig = signature(fn)
                type = sig.return_annotation
                if type is Signature.empty:
                    raise Exception("No return type found, provide a type.")
        self.register_hook(lambda p: issubclass(p.annotation, type), fn)

    def register_hook(self, predicate: PredicateFn, factory: Callable):
        self.register_hook_factory(predicate, lambda _: factory)

    def register_hook_factory(self, predicate: PredicateFn, hook_factory: Callable):
        self.hook_factory_registry.insert(0, (predicate, hook_factory))
        self._invoke_cache.cache_clear()

    def _incant(self, fn: Callable, args: Tuple[Any], kwargs, is_async: bool = False):
        prepared_fn = (
            self._invoke_cache(fn)
            if not is_async
            else self._invoke_cache(fn, is_async=True)
        )
        pos_args_by_type = {a.__class__: a for a in args}
        kwargs_by_name_and_type = {(k, v.__class__): v for k, v in kwargs.items()}
        prepared_args = []
        prepared_kwargs = {}
        sig = signature(prepared_fn)
        for arg_name, arg in sig.parameters.items():
            if (
                arg.annotation is not Signature.empty
                and (arg_name, arg.annotation) in kwargs_by_name_and_type
            ):
                prepared_args.append(
                    kwargs_by_name_and_type[(arg_name, arg.annotation)]
                )
            elif (
                arg.annotation is not Signature.empty
                and arg.annotation in pos_args_by_type
            ):
                prepared_args.append(pos_args_by_type[arg.annotation])
            elif arg_name in kwargs:
                prepared_args.append(kwargs[arg_name])
            else:
                raise TypeError(f"Cannot fulfil argument {arg_name}")
        return prepared_fn(*prepared_args, **prepared_kwargs)

    def _gen_dep_tree(self, fn: Callable) -> List[Tuple[Callable, List[Dep]]]:
        """Generate the dependency tree for `fn` given the current hook reg."""
        to_process = [fn]
        final_nodes = []
        while to_process:
            _nodes = to_process
            to_process = []
            for node in _nodes:
                sig = signature(node)
                dependents = []
                for name, param in sig.parameters.items():
                    if node is not fn and param.default is not Signature.empty:
                        # Do not expose optional params of dependencies.
                        continue
                    param_type = param.annotation
                    for predicate, hook_factory in self.hook_factory_registry:
                        if predicate(param):
                            # Match!
                            factory = hook_factory(param)
                            to_process.append(factory)
                            dependents.append(FactoryDep(factory, name))
                            break
                    else:
                        dependents.append(ParameterDep(name, param_type))
                final_nodes.insert(0, (node, dependents))
        return final_nodes

    def _gen_fn(self, fn: Callable, is_async: Optional[bool] = False):
        dep_tree = self._gen_dep_tree(fn)

        local_vars = []

        # is_async = None means autodetect
        if is_async is None:
            is_async = any(iscoroutinefunction(factory) for factory, _ in dep_tree)
        # All non-parameter deps become local vars.
        for factory, deps in dep_tree[:-1]:
            if not is_async and iscoroutinefunction(factory):
                raise Exception(
                    f"The function would be a coroutine because of {factory}, use `ainvoke` instead"
                )
            deps = [dep.factory if isinstance(dep, FactoryDep) else dep for dep in deps]
            local_vars.append(
                LocalVarFactory(
                    factory,
                    deps,
                )
            )

        outer_args = [
            dep for node in dep_tree for dep in node[1] if isinstance(dep, ParameterDep)
        ]
        # We need to do a pass over the outer args to consolidate duplicates.
        per_outer_arg: dict[str, List[ParameterDep]] = {}
        for arg in outer_args:
            per_outer_arg.setdefault(arg.arg_name, []).append(arg)

        outer_args = []
        for arg_name, args in per_outer_arg.items():
            if len(args) == 1:
                arg_type = args[0].type
            else:
                # If there are multiple competing argument defs,
                # we need to pick a winning type.
                arg_type = Signature.empty
                for arg in args:
                    try:
                        arg_type = _reconcile_types(arg_type, arg.type)
                    except Exception:
                        raise Exception(
                            f"Unable to reconcile types {arg_type} and {arg.type} for argument {arg_name}"
                        )
            outer_args.append(ParameterDep(arg_name, arg_type))

        return compile_fn(fn, outer_args, local_vars, is_async=is_async)


def _reconcile_types(type_a, type_b):
    if type_a is Signature.empty:
        return type_b
    if type_b is Signature.empty:
        return type_a
    raise Exception(f"Unable to reconcile types {type_a!r} and {type_b!r}")
