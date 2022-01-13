from functools import lru_cache
from inspect import Parameter, Signature, iscoroutinefunction, signature
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from attr import Factory, define, field, frozen

from ._codegen import (
    LocalVarFactory,
    ParameterDep,
    compile_fn,
    compile_incant_wrapper,
)


_type = type


R = TypeVar("R")


@define
class FactoryDep:
    factory: Callable
    arg_name: str


Dep = Union[FactoryDep, ParameterDep]


PredicateFn = Callable[[Parameter], bool]


@frozen
class Hook:
    predicate: PredicateFn
    factory: Callable[[Parameter], Callable]

    @classmethod
    def for_name(cls, name: str, hook: Callable):
        return cls(lambda p: p.name == name, lambda _: hook)

    @classmethod
    def for_type(cls, type: Any, hook: Callable):
        """Register by exact type (subclasses won't match)."""
        return cls(lambda p: p.annotation == type, lambda _: hook)


@define
class Incanter:
    hook_factory_registry: List[Hook] = Factory(list)
    _invoke_cache: Callable = field(
        init=False,
        default=Factory(
            lambda self: lru_cache(None)(self._gen_invoke), takes_self=True
        ),
    )
    _incant_cache: Callable = field(
        init=False,
        default=Factory(
            lambda self: lru_cache(None)(self._gen_incant), takes_self=True
        ),
    )

    def prepare(
        self,
        fn: Callable[..., R],
        hooks: Sequence[Hook] = (),
        is_async: Optional[bool] = None,
    ) -> Callable[..., R]:
        return self._invoke_cache(fn, tuple(hooks), is_async)

    def invoke(self, fn: Callable[..., R], *args, **kwargs) -> R:
        return self.prepare(fn, is_async=False)(*args, **kwargs)

    async def ainvoke(self, fn: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
        return await self.prepare(fn, is_async=True)(*args, **kwargs)

    def incant(self, fn: Callable[..., R], *args, **kwargs) -> R:
        """Invoke `fn` the best way we can."""
        return self._incant(fn, args, kwargs)

    async def aincant(self, fn: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
        """Invoke async `fn` the best way we can."""
        return await self._incant(fn, args, kwargs, is_async=True)

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

    def register_by_type(self, fn: Union[Callable, Type], type: Optional[Type] = None):
        """
        Register a factory to be injected by type. Can also be used as a decorator.

        If the type is not provided, the return annotation from the
        factory will be used.
        """
        if type is None:
            if isinstance(fn, _type):
                type_to_reg = fn
            else:
                sig = signature(fn)
                type_to_reg = sig.return_annotation
                if type_to_reg is Signature.empty:
                    raise Exception("No return type found, provide a type.")
        else:
            type_to_reg = type
        self.register_hook(lambda p: issubclass(p.annotation, type_to_reg), fn)

    def register_hook(self, predicate: PredicateFn, factory: Callable):
        self.register_hook_factory(predicate, lambda _: factory)

    def register_hook_factory(
        self, predicate: PredicateFn, hook_factory: Callable[[Parameter], Callable]
    ):
        self.hook_factory_registry.insert(0, Hook(predicate, hook_factory))
        self._invoke_cache.cache_clear()  # type: ignore
        self._incant_cache.cache_clear()  # type: ignore

    def _incant(
        self,
        fn: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        is_async: bool = False,
    ):
        """The shared entrypoint for ``incant`` and ``aincant``."""

        pos_args_types = tuple([a.__class__ for a in args])
        kwargs_by_name_and_type = frozenset(
            [(k, v.__class__) for k, v in kwargs.items()]
        )
        wrapper = self._incant_cache(
            fn, pos_args_types, kwargs_by_name_and_type, is_async
        )

        return wrapper(*args, **kwargs)

    def _gen_incant_plan(
        self, fn, pos_args_types: Tuple, kwargs: Set[Tuple[str, Any]], is_async=False
    ) -> List[Union[int, str]]:
        """Generate a plan to invoke `fn`, potentially using `args` and `kwargs`."""
        pos_arg_plan: List[Union[int, str]] = []
        prepared_fn = (
            self._invoke_cache(fn)
            if not is_async
            else self._invoke_cache(fn, is_async=True)
        )
        pos_args_by_type = {a: ix for ix, a in enumerate(pos_args_types)}
        kwarg_names = {kw[0] for kw in kwargs}
        sig = signature(prepared_fn)
        for arg_name, arg in sig.parameters.items():
            if (
                arg.annotation is not Signature.empty
                and (arg_name, arg.annotation) in kwargs
            ):
                pos_arg_plan.append(arg_name)
            elif (
                arg.annotation is not Signature.empty
                and arg.annotation in pos_args_by_type
            ):
                pos_arg_plan.append(pos_args_by_type[arg.annotation])
            elif arg_name in kwarg_names:
                pos_arg_plan.append(arg_name)
            else:
                raise TypeError(f"Cannot fulfil argument {arg_name}")
        return pos_arg_plan

    def _gen_incant(
        self,
        fn: Callable,
        pos_args_types: Tuple,
        kwargs_by_name_and_type: Set,
        is_async: Optional[bool] = False,
    ) -> Callable:
        prepared_fn = (
            self._invoke_cache(fn)
            if not is_async
            else self._invoke_cache(fn, is_async=True)
        )
        plan = self._gen_incant_plan(
            prepared_fn, pos_args_types, kwargs_by_name_and_type, is_async=is_async
        )
        incant = compile_incant_wrapper(
            prepared_fn, plan, len(pos_args_types), len(kwargs_by_name_and_type)
        )
        return incant

    def _gen_dep_tree(
        self, fn: Callable, additional_hooks: Sequence[Hook]
    ) -> List[Tuple[Callable, List[Dep]]]:
        """Generate the dependency tree for `fn`."""
        to_process = [fn]
        final_nodes: List[Tuple[Callable, List[Dep]]] = []
        hooks = list(additional_hooks) + self.hook_factory_registry
        while to_process:
            _nodes = to_process
            to_process = []
            for node in _nodes:
                sig = signature(node)
                dependents: List[Union[ParameterDep, FactoryDep]] = []
                for name, param in sig.parameters.items():
                    if node is not fn and param.default is not Signature.empty:
                        # Do not expose optional params of dependencies.
                        continue
                    param_type = param.annotation
                    for hook in hooks:
                        if hook.predicate(param):
                            # Match!
                            factory = hook.factory(param)
                            to_process.append(factory)
                            dependents.append(FactoryDep(factory, name))
                            break
                    else:
                        dependents.append(ParameterDep(name, param_type))
                final_nodes.insert(0, (node, dependents))
        return final_nodes

    def _gen_invoke(
        self,
        fn: Callable,
        hooks: Tuple[Hook, ...] = (),
        is_async: Optional[bool] = False,
    ):
        dep_tree = self._gen_dep_tree(fn, hooks)

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
            local_vars.append(
                LocalVarFactory(
                    factory,
                    [
                        dep.factory if isinstance(dep, FactoryDep) else dep
                        for dep in deps
                    ],
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
