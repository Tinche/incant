import sys

from functools import partial
from inspect import Parameter
from inspect import signature as sig
from typing import Any, Optional

from attr import frozen


NO_OVERRIDE = object()


@frozen
class Override:
    name: Optional[str] = None
    annotation: Any = NO_OVERRIDE


if sys.version_info >= (3, 9):
    from typing import _AnnotatedAlias  # type: ignore

else:
    from typing_extensions import _AnnotatedAlias

if sys.version_info >= (3, 10):
    signature = partial(sig, eval_str=True)

else:
    signature = sig


def get_annotated_override(p: Parameter) -> Parameter:
    if p.annotation.__class__ is _AnnotatedAlias:
        for arg in p.annotation.__metadata__:
            if isinstance(arg, Override):
                name = arg.name if arg.name is not None else p.name
                an = (
                    arg.annotation
                    if arg.annotation is not NO_OVERRIDE
                    else p.annotation
                )
                return Parameter(name, p.kind, default=p.default, annotation=an)
    return p
