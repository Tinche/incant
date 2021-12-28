import linecache
import uuid

from collections.abc import Mapping
from functools import lru_cache
from inspect import Parameter, Signature, signature
from typing import Any, Callable, TypeVar, Union

from attr import Factory, define
from rich import print


R = TypeVar("R")


@define
class FactoryDep:
    factory: Callable
    arg_name: str


@define
class ParameterDep:
    arg_name: str
    type: Any


Dep = Union[FactoryDep, ParameterDep]


@define
class LocalVarConstant:
    factory: Callable
    value: Any


@define
class LocalVarFactory:
    factory: Callable
    args: list[Union[Callable, ParameterDep]]


LocalVar = Union[LocalVarConstant, LocalVarFactory]


def _compile_fn(
    fn,
    outer_args: list[ParameterDep],
    local_vars: list[LocalVar],
) -> Callable:
    # Some arguments need to be taken from outside.
    # Some arguments need to be calculated from factories.
    fn_name = f"invoke_{fn.__name__}"
    globs = {"_incant_inner_fn": fn}
    arg_lines = []
    for dep in outer_args:
        if dep.type is not Signature.empty:
            arg_type_snippet = f": _incant_arg_{dep.arg_name}"
            globs[f"_incant_arg_{dep.arg_name}"] = dep.type
        else:
            arg_type_snippet = ""

        arg_lines.append(f"{dep.arg_name}{arg_type_snippet}")
    outer_arg_names = {o.arg_name for o in outer_args}

    lines = []
    lines.append(f"def {fn_name}({', '.join(arg_lines)}):")
    local_vars_ix_by_factory = {
        local_var.factory: ix for ix, local_var in enumerate(local_vars)
    }
    for i, local_var in enumerate(local_vars):
        local_name = f"_incant_local_{i}"
        if isinstance(local_var, LocalVarConstant):
            local_var_local_val = f"_incant_local_val_{i}"
            lines.append(f"  {local_name} = {local_var_local_val}")
            globs[local_var_local_val] = local_var.value
        else:
            local_var_factory = f"_incant_local_factory_{i}"
            globs[local_var_factory] = local_var.factory
            local_arg_lines = []
            for local_arg in local_var.args:
                if isinstance(local_arg, ParameterDep):
                    local_arg_lines.append(local_arg.arg_name)
                else:
                    local_arg_lines.append(
                        f"_incant_local_{local_vars_ix_by_factory[local_arg]}"
                    )
            lines.append(
                f"  {local_name} = {local_var_factory}({', '.join(local_arg_lines)})"
            )

    incant_arg_lines = []
    local_var_ix = len(local_vars) - 1
    for name in signature(fn).parameters:
        if name in outer_arg_names:
            incant_arg_lines.append(name)
        else:
            incant_arg_lines.append(f"_incant_local_{local_var_ix}")
            local_var_ix -= 1

    lines.append(f"  return _incant_inner_fn({', '.join(incant_arg_lines)})")

    script = "\n".join(lines)
    print(script)

    fname = _generate_unique_filename(fn.__name__)
    eval(compile(script, fname, "exec"), globs)

    fn = globs[fn_name]
    return fn


@define(slots=False)
class Incanter:
    hook_registry: list = Factory(list)

    def __attrs_post_init__(self):
        self._gen_fn = lru_cache(None)(self._gen_fn)

    def invoke(self, fn, *args, **kwargs):
        return self._gen_fn(fn)(*args, **kwargs)

    def incant(self, fn: Callable[..., R], *args, **kwargs) -> R:
        """Invoke `fn` the best way we can."""
        prepared_fn = self._gen_fn(fn)
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

    def _gen_dep_tree(self, fn: Callable) -> list[tuple[Callable, list[Dep]]]:
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
                    param_type = param.annotation
                    for predicate, factory in self.hook_registry:
                        if predicate(name, param_type):
                            # Match!
                            to_process.append(factory)
                            dependents.append(FactoryDep(factory, name))
                            break
                    else:
                        dependents.append(ParameterDep(name, param_type))
                final_nodes.insert(0, (node, dependents))
        return final_nodes

    def _gen_fn(self, fn: Callable):
        dep_tree = self._gen_dep_tree(fn)

        local_vars = []
        # All non-parameter deps become local vars.
        for factory, deps in dep_tree[:-1]:
            if not deps:
                local_vars.append(LocalVarConstant(factory, factory()))
            else:
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
        per_outer_arg: dict[str, list[ParameterDep]] = {}
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

        return _compile_fn(fn, outer_args, local_vars)

    def parameters(self, fn: Callable) -> Mapping[str, Parameter]:
        """Return the signature needed to successfully and exactly invoke `fn`."""
        return signature(self._gen_fn(fn)).parameters

    def register_hook(self, predicate: Callable[[str, Any], bool], factory: Callable):
        self.hook_registry.append((predicate, factory))
        self._gen_fn.cache_clear()


def _generate_unique_filename(func_name, reserve=True):
    """
    Create a "filename" suitable for a function being generated.
    """
    unique_id = uuid.uuid4()
    extra = ""
    count = 1

    while True:
        unique_filename = "<incant generated incant of {0}{1}>".format(
            func_name,
            extra,
        )
        if not reserve:
            return unique_filename
        # To handle concurrency we essentially "reserve" our spot in
        # the linecache with a dummy line.  The caller can then
        # set this value correctly.
        cache_line = (1, None, (str(unique_id),), unique_filename)
        if linecache.cache.setdefault(unique_filename, cache_line) == cache_line:
            return unique_filename

        # Looks like this spot is taken. Try again.
        count += 1
        extra = "-{0}".format(count)


def _reconcile_types(type_a, type_b):
    if type_a is Signature.empty:
        return type_b
    if type_b is Signature.empty:
        return type_a
    raise Exception(f"Unable to reconcile types {type_a!r} and {type_b!r}")
