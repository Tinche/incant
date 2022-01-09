import linecache
import uuid

from contextlib import AbstractAsyncContextManager
from inspect import (
    Signature,
    isasyncgenfunction,
    iscoroutinefunction,
    signature,
)
from time import time
from typing import Any, Callable, List, Union

from attr import define


def _is_async_context_manager(fn: Any) -> bool:
    return (
        fn.__class__ is type and issubclass(fn, AbstractAsyncContextManager)
    ) or bool(
        (wrapped := getattr(fn, "__wrapped__", None)) and isasyncgenfunction(wrapped)
    )


@define
class ParameterDep:
    arg_name: str
    type: Any


@define
class LocalVarFactory:
    factory: Callable
    args: List[Union[Callable, ParameterDep]]


def compile_fn(
    fn: Callable,
    outer_args: List[ParameterDep],
    local_vars: List[LocalVarFactory],
    is_async: bool = False,
) -> Callable:
    # Some arguments need to be taken from outside.
    # Some arguments need to be calculated from factories.
    fn_name = f"invoke_{fn.__name__}" if fn.__name__ != "<lambda>" else "invoke_lambda"
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
    if is_async:
        lines.append(f"async def {fn_name}({', '.join(arg_lines)}):")
    else:
        lines.append(f"def {fn_name}({', '.join(arg_lines)}):")
    local_vars_ix_by_factory = {
        local_var.factory: ix for ix, local_var in enumerate(local_vars)
    }
    ind = 0  # Indentation level
    for i, local_var in enumerate(local_vars):
        local_name = f"_incant_local_{i}"
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
        if _is_async_context_manager(local_var.factory):
            lines.append(
                f"  {' ' * ind}async with {local_var_factory}({', '.join(local_arg_lines)}) as {local_name}:"
            )
            ind += 2
        else:
            aw = ""
            if iscoroutinefunction(local_var.factory):
                aw = "await "
            lines.append(
                f"  {' ' * ind}{local_name} = {aw}{local_var_factory}({', '.join(local_arg_lines)})"
            )

    incant_arg_lines = []
    local_var_ix = len(local_vars) - 1
    for name in signature(fn).parameters:
        if name in outer_arg_names:
            incant_arg_lines.append(name)
        else:
            incant_arg_lines.append(f"_incant_local_{local_var_ix}")
            local_var_ix -= 1

    aw = ""
    if iscoroutinefunction(fn):
        aw = "await "
    lines.append(
        f"  {' ' * ind}return {aw}_incant_inner_fn({', '.join(incant_arg_lines)})"
    )

    script = "\n".join(lines)

    fname = _generate_unique_filename(fn.__name__, "invoke")
    eval(compile(script, fname, "exec"), globs)

    fn = globs[fn_name]
    return fn


def compile_incant_wrapper(
    fn: Callable, incant_plan: List[Union[int, str]], num_pos_args: int, num_kwargs: int
):
    fn_name = f"incant_{fn.__name__}" if fn.__name__ != "<lambda>" else "incant_lambda"
    globs = {"_incant_inner_fn": fn}
    arg_lines = []
    if incant_plan:
        if num_pos_args:
            arg_lines.append("*args")
        else:
            arg_lines.append("*")

    kwargs = [arg for arg in incant_plan if isinstance(arg, str)]
    arg_lines.extend(kwargs)
    if num_kwargs > len(kwargs):
        arg_lines.append("**kwargs")

    lines = []
    lines.append(f"def {fn_name}({', '.join(arg_lines)}):")
    lines.append("  return _incant_inner_fn(")
    for arg in incant_plan:
        if isinstance(arg, int):
            lines.append(f"    args[{arg}],")
        else:
            lines.append(f"    {arg},")
    lines.append("  )")

    script = "\n".join(lines)

    fname = _generate_unique_filename(fn.__name__, "incant")
    eval(compile(script, fname, "exec"), globs)

    fn = globs[fn_name]
    return fn


def _generate_unique_filename(func_name: str, func_type: str):
    """
    Create a "filename" suitable for a function being generated.
    """
    unique_id = uuid.uuid4()
    extra = ""
    count = 1

    while True:
        unique_filename = f"<incant generated {func_type} of {func_name}{extra}>"
        # To handle concurrency we essentially "reserve" our spot in
        # the linecache with a dummy line.  The caller can then
        # set this value correctly.
        cache_line = (1, time(), [str(unique_id)], unique_filename)
        if linecache.cache.setdefault(unique_filename, cache_line) == cache_line:
            return unique_filename

        # Looks like this spot is taken. Try again.
        count += 1
        extra = f"-{count}"
