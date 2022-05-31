import linecache

from inspect import Signature, iscoroutinefunction, signature
from typing import Any, Callable, List, Literal, Optional, Union

from attr import define


@define
class ParameterDep:
    arg_name: str
    type: Any
    default: Any = Signature.empty


CtxManagerKind = Literal["sync", "async"]


@define
class LocalVarFactory:
    factory: Callable
    args: List[Union[Callable, ParameterDep]]
    is_forced: bool = False
    is_ctx_manager: Optional[CtxManagerKind] = None


def compile_invoke(
    fn: Callable,
    fn_factory_args: List[str],
    outer_args: List[ParameterDep],
    local_vars: List[LocalVarFactory],
    is_async: bool = False,
) -> Callable:
    # Some arguments need to be taken from outside.
    # Some arguments need to be calculated from factories.
    sig = signature(fn)
    fn_name = f"invoke_{fn.__name__}" if fn.__name__ != "<lambda>" else "invoke_lambda"
    globs = {"_incant_inner_fn": fn}
    taken_local_vars = set()
    arg_lines = []

    for dep in outer_args:
        if dep.type is not Signature.empty:
            type_name = dep.type.__name__
            if type_name not in globs or globs[type_name] is dep.type:
                arg_type_snippet = f": {type_name}"
                globs[type_name] = dep.type
            else:
                arg_type_snippet = f": _incant_arg_{dep.arg_name}"
                globs[f"_incant_arg_{dep.arg_name}"] = dep.type
        else:
            arg_type_snippet = ""
        if dep.default is not Signature.empty:
            arg_default = f"_incant_default_{dep.arg_name}"
            arg_type_snippet = f"{arg_type_snippet} = {arg_default}"
            globs[arg_default] = dep.default

        arg_lines.append(f"{dep.arg_name}{arg_type_snippet}")
        taken_local_vars.add(dep.arg_name)
    outer_arg_names = {o.arg_name for o in outer_args}

    lines = []

    ret_type = ""
    if sig.return_annotation is not Signature.empty:
        tn = getattr(sig.return_annotation, "__name__", None)
        if tn is None or tn in globs and globs[tn] is not sig.return_annotation:
            tn = "_incant_return_type"
        globs[tn] = sig.return_annotation
        ret_type = f" -> {tn}"
    if is_async:
        lines.append(f"async def {fn_name}({', '.join(arg_lines)}){ret_type}:")
    else:
        lines.append(f"def {fn_name}({', '.join(arg_lines)}){ret_type}:")
    local_vars_ix_by_factory = {
        local_var.factory: ix for ix, local_var in enumerate(local_vars)
    }
    ind = 0  # Indentation level

    local_counter = 0

    for i, local_var in enumerate(local_vars):
        local_var_fn = local_var.factory.__name__

        if local_var_fn not in taken_local_vars and local_var_fn != "<lambda>":
            local_var_factory_name = local_var_fn
        else:
            local_var_factory_name = f"_incant_local_factory_{i}"
        globs[local_var_factory_name] = local_var.factory

        local_arg_lines = []
        for local_arg in local_var.args:
            if isinstance(local_arg, ParameterDep):
                local_arg_lines.append(local_arg.arg_name)
            else:
                local_arg_lines.append(
                    f"_incant_local_{local_vars_ix_by_factory[local_arg]}"
                )

        local_name = f"_incant_local_{local_counter}"

        if local_var.is_ctx_manager is not None:
            aw = "async " if local_var.is_ctx_manager == "async" else ""
            if not local_var.is_forced:
                lines.append(
                    f"  {' ' * ind}{aw}with {local_var_factory_name}({', '.join(local_arg_lines)}) as {local_name}:"
                )
                local_counter += 1
            else:
                lines.append(
                    f"  {' ' * ind}{aw}with {local_var_factory_name}({', '.join(local_arg_lines)}):"
                )
            ind += 2
        else:

            aw = "await " if iscoroutinefunction(local_var.factory) else ""
            if not local_var.is_forced:
                lines.append(
                    f"  {' ' * ind}{local_name} = {aw}{local_var_factory_name}({', '.join(local_arg_lines)})"
                )
                local_counter += 1
            else:
                lines.append(
                    f"  {' ' * ind}{aw}{local_var_factory_name}({', '.join(local_arg_lines)})"
                )

    incant_arg_lines = []
    local_var_ix = len([lv for lv in local_vars if not lv.is_forced]) - 1
    for name in sig.parameters:
        if name not in fn_factory_args and name in outer_arg_names:
            incant_arg_lines.append(name)
        else:
            incant_arg_lines.append(f"_incant_local_{local_var_ix}")
            local_var_ix -= 1

    aw = "await " if iscoroutinefunction(fn) else ""
    lines.append(
        f"  {' ' * ind}return {aw}_incant_inner_fn({', '.join(incant_arg_lines)})"
    )

    script = "\n".join(lines)

    fname = _generate_unique_filename(fn.__name__, "invoke", lines)
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

    fname = _generate_unique_filename(fn.__name__, "incant", lines)
    eval(compile(script, fname, "exec"), globs)

    fn = globs[fn_name]
    return fn


def _generate_unique_filename(func_name: str, func_type: str, source: List[str]):
    """
    Create a "filename" suitable for a function being generated.
    """
    extra = ""
    count = 1

    while True:
        unique_filename = f"<incant generated {func_type} of {func_name}{extra}>"
        # To handle concurrency we essentially "reserve" our spot in
        # the linecache with a dummy line.  The caller can then
        # set this value correctly.
        cache_line = (len(source), None, source, unique_filename)
        if linecache.cache.setdefault(unique_filename, cache_line) == cache_line:  # type: ignore
            return unique_filename

        # Looks like this spot is taken. Try again.
        count += 1
        extra = f"-{count}"
