from functools import lru_cache
from inspect import Parameter, Signature, iscoroutinefunction
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
    CtxManagerKind,
    Invocation,
    ParameterDep,
    compile_compose,
    compile_incant_wrapper,
)
from ._compat import NO_OVERRIDE, Override, get_annotated_override, signature


__all__ = ["NO_OVERRIDE", "Override", "Hook", "Incanter", "IncantError"]

_type = type


R = TypeVar("R")


@frozen
class FactoryDep:
    factory: Callable  # The fn to call.
    arg_name: str  # The name of the param this is fulfulling.
    # Is the result of the factory a ctx manager?
    is_ctx_manager: Optional[CtxManagerKind] = None


Dep = Union[FactoryDep, ParameterDep]


PredicateFn = Callable[[Parameter], bool]


def is_subclass(type, superclass) -> bool:
    """A safe version of `issubclass`."""
    try:
        return issubclass(type, superclass)
    except Exception:
        return False


@frozen
class Hook:
    predicate: PredicateFn
    factory: Optional[Tuple[Callable[[Parameter], Callable], Optional[CtxManagerKind]]]

    @classmethod
    def for_name(cls, name: str, hook: Optional[Callable]) -> "Hook":
        return cls(lambda p: p.name == name, None if hook is None else (lambda _: hook, None))  # type: ignore

    @classmethod
    def for_type(cls, type: Any, hook: Optional[Callable]) -> "Hook":
        """Register by exact type (subclasses won't match)."""
        return cls(
            lambda p: p.annotation == type,
            None if hook is None else (lambda _: hook, None),  # type: ignore
        )


@define
class Incanter:
    """A registry of _hooks_, used for function composition.

    Hooks use predicate functions to define rules of how they bind to function
    arguments.
    """

    hook_factory_registry: List[Hook] = Factory(list)
    _call_cache: Callable = field(
        init=False,
        default=Factory(lambda self: lru_cache(None)(self._gen_call), takes_self=True),
    )
    _incant_cache: Callable = field(
        init=False,
        default=Factory(
            lambda self: lru_cache(None)(self._gen_incant), takes_self=True
        ),
    )

    def compose(
        self,
        fn: Callable[..., R],
        hooks: Sequence[Hook] = (),
        is_async: Optional[bool] = None,
        forced_deps: Sequence[Union[Callable, Tuple[Callable, CtxManagerKind]]] = (),
    ) -> Callable[..., R]:
        """Compose `fn` with its satisfied dependencies, potentially creating a new function.

        :param forced_deps: A sequence of dependencies that will be used even if `fn`
            doesn't require them explicitly.
        """
        return self._call_cache(
            fn,
            tuple(hooks),
            is_async,
            tuple(f if isinstance(f, tuple) else (f, None) for f in forced_deps),
        )

    def compose_and_call(self, fn: Callable[..., R], *args, **kwargs) -> R:
        """Compose `fn` and call it with the given parameters."""
        return self.compose(fn, is_async=False)(*args, **kwargs)

    invoke = compose_and_call

    async def acompose_and_call(
        self, fn: Callable[..., Awaitable[R]], *args, **kwargs
    ) -> R:
        """Compose `fn` as async and call it with the given parameters."""
        return await self.compose(fn, is_async=True)(*args, **kwargs)

    ainvoke = acompose_and_call

    def incant(self, fn: Callable[..., R], *args, **kwargs) -> R:
        """Invoke `fn` the best way we can."""
        return self._incant(fn, args, kwargs)

    async def aincant(self, fn: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
        """Invoke async `fn` the best way we can."""
        return await self._incant(fn, args, kwargs)

    def adapt(
        self, fn: Callable[..., R], *args: PredicateFn, **kwargs: PredicateFn
    ) -> Callable[..., R]:
        """Adapt `fn` for incantation.

        Args and kwargs shape the signature of the produced function.
        """
        return self._incant_cache(
            fn, args, frozenset((k, v) for k, v in kwargs.items())
        )

    def register_by_name(
        self,
        fn: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        is_ctx_manager: Optional[CtxManagerKind] = None,
    ):
        """
        Register a factory to be injected by name. Can also be used as a decorator.

        If the name is not provided, the name of the factory will be used.
        """
        if fn is None:
            # Decorator
            return lambda fn: self.register_by_name(
                fn, name=name, is_ctx_manager=is_ctx_manager
            )

        if name is None:
            name = fn.__name__
        self.register_hook(lambda p: p.name == name, fn, is_ctx_manager=is_ctx_manager)
        return fn

    def register_by_type(
        self,
        fn: Union[Callable, Type],
        type: Optional[Type] = None,
        is_ctx_manager: Optional[CtxManagerKind] = None,
    ):
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
                    raise IncantError("No return type found, provide a type.")
        else:
            type_to_reg = type
        self.register_hook(
            lambda p: p.annotation == type_to_reg
            or is_subclass(p.annotation, type_to_reg),
            fn,
            is_ctx_manager,
        )
        return fn

    def register_hook(
        self,
        predicate: PredicateFn,
        factory: Callable,
        is_ctx_manager: Optional[CtxManagerKind] = None,
    ) -> None:
        """Register a hook to be used for function composition.

        :param predicate: A predicate function, should return `True` if this hook
            should be used to fulfill a function parameter.
        :param factory: The function that will be called to fulfil a function
            parameter.
        :param is_ctx_manager: Is the `factory` a context manager?
        """
        self.register_hook_factory(predicate, lambda _: factory, is_ctx_manager)

    def register_hook_factory(
        self,
        predicate: PredicateFn,
        hook_factory: Callable[[Parameter], Callable],
        is_ctx_manager: Optional[CtxManagerKind] = None,
    ) -> None:
        self.hook_factory_registry.insert(
            0, Hook(predicate, (hook_factory, is_ctx_manager))
        )
        self._call_cache.cache_clear()  # type: ignore
        self._incant_cache.cache_clear()  # type: ignore

    def _incant(
        self,
        fn: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ):
        """The shared entrypoint for ``incant`` and ``aincant``."""

        pos_args = tuple(
            lambda p, c=a.__class__: is_subclass(c, p.annotation) for a in args
        )
        kwargs_by_name_and_pred = frozenset(
            [
                (k, lambda p, c=v.__class__: is_subclass(c, p.annotation))
                for k, v in kwargs.items()
            ]
        )
        wrapper = self._incant_cache(fn, pos_args, kwargs_by_name_and_pred)

        return wrapper(*args, **kwargs)

    def _gen_incant_plan(
        self,
        fn: Callable,
        pos_args: Tuple[PredicateFn, ...],
        kwargs: Dict[str, PredicateFn],
    ) -> List[Union[int, str]]:
        """Generate a plan to invoke `fn`, potentially using `args` and `kwargs`."""
        pos_arg_plan: List[Union[int, str]] = []
        sig = signature(fn)
        for arg_name, arg in sig.parameters.items():
            found = False

            for kwarg_pred in kwargs.values():
                if kwarg_pred(arg):
                    pos_arg_plan.append(arg_name)
                    found = True
                    break
            if found:
                continue

            if arg.annotation is not Signature.empty:
                for ix, pred in enumerate(pos_args):
                    if pred(arg):
                        pos_arg_plan.append(ix)
                        found = True
                        break
            if found:
                continue

            if arg_name in kwargs:
                pos_arg_plan.append(arg_name)
            elif arg.default is not Signature.empty:
                # An argument with a default we cannot fulfil is ok.
                continue
            else:
                raise TypeError(f"Cannot fulfil argument {arg_name}")
        return pos_arg_plan

    def _gen_incant(
        self,
        fn: Callable,
        pos_args: Tuple[PredicateFn, ...],
        kwargs: Set[Tuple[str, PredicateFn]],
    ) -> Callable:
        plan = self._gen_incant_plan(fn, pos_args, dict(kwargs))
        return compile_incant_wrapper(fn, plan, len(pos_args), len(kwargs))

    def _gen_dep_tree(
        self,
        fn: Callable,
        additional_hooks: Sequence[Hook],
        forced_deps: Sequence[Tuple[Callable, Optional[CtxManagerKind]]] = (),
    ) -> List[Tuple[Callable, Optional[CtxManagerKind], List[Dep]]]:
        """Generate the dependency tree for `fn`.

        The dependency tree is a list of factories and their dependencies.

        The actual function is the last item.
        """
        to_process = [(fn, None), *forced_deps]
        final_nodes: List[Tuple[Callable, Optional[CtxManagerKind], List[Dep]]] = []
        hooks = list(additional_hooks) + self.hook_factory_registry
        already_processed_hooks = set()
        while to_process:
            _nodes = to_process
            to_process = []
            for node, ctx_mgr_kind in _nodes:
                sig = _signature(node)
                dependents: List[Union[ParameterDep, FactoryDep]] = []
                for name, param in sig.parameters.items():
                    if (
                        node is not fn
                        and param.default is not Signature.empty
                        and param.kind is Parameter.KEYWORD_ONLY
                    ):
                        # Do not expose optional kw-only params of dependencies.
                        continue
                    param_type = param.annotation
                    for hook in hooks:
                        if hook.predicate(param):
                            # Match!
                            if hook.factory is None:
                                dependents.append(
                                    ParameterDep(name, param_type, param.default)
                                )
                            else:
                                factory = hook.factory[0](param)
                                if factory == node:
                                    # A hook cannot satisfy itself.
                                    continue
                                if factory not in already_processed_hooks:
                                    to_process.append((factory, hook.factory[1]))
                                    already_processed_hooks.add(factory)
                                dependents.append(
                                    FactoryDep(factory, name, hook.factory[1])
                                )

                            break
                    else:
                        dependents.append(ParameterDep(name, param_type, param.default))
                final_nodes.insert(0, (node, ctx_mgr_kind, dependents))

        # We need to sort the nodes to ensure no unbound local vars.
        dep_nodes = final_nodes[:-1]
        dep_nodes.sort(key=lambda n: len(n[2]))
        dep_nodes.append(final_nodes[-1])
        return dep_nodes

    def _gen_call(
        self,
        fn: Callable,
        hooks: Tuple[Hook, ...] = (),
        is_async: Optional[bool] = False,
        forced_deps: Tuple[Tuple[Callable, CtxManagerKind], ...] = (),
    ):
        dep_tree = self._gen_dep_tree(fn, hooks, forced_deps)
        if len(dep_tree) == 1 and (
            is_async is None or (is_async is iscoroutinefunction(fn))
        ):
            # Nothing we can do for this function.
            return fn

        # is_async = None means autodetect
        if is_async is None:
            is_async = any(
                iscoroutinefunction(factory) or ctx_mgr_kind == "async"
                for factory, ctx_mgr_kind, _ in dep_tree
            )

        invocs: List[Invocation] = []
        # All non-parameter deps become invocations.
        for ix, (factory, ctx_mgr_kind, deps) in enumerate(dep_tree[:-1]):
            if not is_async and (
                iscoroutinefunction(factory) or ctx_mgr_kind == "async"
            ):
                raise TypeError(
                    f"The function would be a coroutine because of {factory}, use `ainvoke` instead"
                )

            # It's possible this is a forced dependency, and nothing downstream actually needs it.
            # In that case, we mark it as forced so it doesn't get its own local var in the generated function.
            is_needed = False
            for _, _, downstream_deps in dep_tree[ix + 1 :]:
                if any(
                    isinstance(d, FactoryDep) and d.factory == factory
                    for d in downstream_deps
                ):
                    is_needed = True
                    break

            invocs.append(
                Invocation(
                    factory,
                    [
                        dep.factory if isinstance(dep, FactoryDep) else dep
                        for dep in deps
                    ],
                    not is_needed,
                    ctx_mgr_kind,
                )
            )

        outer_args = [
            dep for node in dep_tree for dep in node[2] if isinstance(dep, ParameterDep)
        ]
        # We need to do a pass over the outer args to consolidate duplicates.
        per_outer_arg: dict[str, List[ParameterDep]] = {}
        for arg in outer_args:
            per_outer_arg.setdefault(arg.arg_name, []).append(arg)

        outer_args.clear()
        for arg_name, args in per_outer_arg.items():
            if len(args) == 1:
                arg_type = args[0].type
                arg_default = args[0].default
            else:
                # If there are multiple competing argument defs,
                # we need to pick a winning type.
                arg_type = Signature.empty
                arg_default = Signature.empty
                for arg in args:
                    try:
                        arg_type = _reconcile_types(arg_type, arg.type)
                    except Exception as exc:
                        raise IncantError(
                            f"Unable to reconcile types {arg_type} and {arg.type} for argument {arg_name}"
                        ) from exc
                    if arg.default is not Signature.empty:
                        arg_default = arg.default
            outer_args.append(ParameterDep(arg_name, arg_type, arg_default))

        # outer_args need to be sorted by the presence of a default value
        outer_args.sort(key=lambda a: a.default is not Signature.empty)

        fn_factory_args = []
        fn_factories = []
        for dep in dep_tree[-1][2]:
            if isinstance(dep, FactoryDep):
                fn_factory_args.append(dep.arg_name)
                fn_factories.append(dep.factory)

        return compile_compose(
            fn,
            fn_factories,
            fn_factory_args,
            outer_args,
            invocs,
            is_async=is_async,
        )


def _reconcile_types(type_a, type_b):
    if type_a is Signature.empty:
        return type_b
    if type_b is Signature.empty:
        return type_a
    if type_a is type_b:
        return type_a
    raise Exception(f"Unable to reconcile types {type_a!r} and {type_b!r}")


def _signature(f: Callable) -> Signature:
    """Return the signature of f, with potential overrides applied."""
    sig = signature(f)
    parameters = [get_annotated_override(val) for val in sig.parameters.values()]
    return sig.replace(parameters=parameters)


class IncantError(Exception):
    """An Incant error."""
