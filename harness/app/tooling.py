# 文件：harness/app/tooling.py
from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar, get_type_hints

from pydantic import ConfigDict, create_model

from harness.tools.definition import Tool
from harness.tools.factory import tool_from_pydantic

F = TypeVar("F", bound=Callable[..., Any])
_TOOL_ATTR = "__mini_harness_tool__"


def to_tool(
    func: F,
    *,
    name: str | None = None,
    description: str | None = None,
    timeout_seconds: float = 10.0,
    max_retries: int = 0,
    permissions: tuple[str, ...] = (),
    side_effect: bool = False,
    idempotent: bool = False,
    requires_approval: bool = False,
    inject_context: bool = False,
) -> Tool:
    """把普通有类型注解的 Python 函数转换成内部 Tool Contract。"""
    signature = inspect.signature(func)
    try:
        type_hints = get_type_hints(func)
    except (NameError, TypeError):
        type_hints = {}
    fields: dict[str, tuple[Any, Any]] = {}

    for param in signature.parameters.values():
        if inject_context and param.name == "context":
            continue
        if param.kind not in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }:
            raise TypeError(
                f"Tool '{func.__name__}' 只支持命名参数；不支持 {param.kind}."
            )
        annotation = type_hints.get(
            param.name,
            Any if param.annotation is inspect.Parameter.empty else param.annotation,
        )
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[param.name] = (annotation, default)

    model = create_model(
        f"{func.__name__.title().replace('_', '')}Args",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )
    return tool_from_pydantic(
        name=name or func.__name__,
        description=description or inspect.getdoc(func) or f"调用 {func.__name__}。",
        args_model=model,
        handler=func,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        required_permissions=frozenset(permissions),
        side_effect=side_effect,
        idempotent=idempotent,
        requires_approval=requires_approval,
        source="local",
        inject_context=inject_context,
    )


def get_declared_tool(value) -> Tool | None:
    return getattr(value, _TOOL_ATTR, None)


def tool(func: F | None = None, **options):
    """声明 Tool，但保留原函数本身可调用。

    示例：
        @tool(side_effect=False)
        def add(a: float, b: float) -> float:
            return a + b

        app.add_tool(add)
    """
    def decorate(target: F) -> F:
        setattr(target, _TOOL_ATTR, to_tool(target, **options))
        return target

    if func is not None:
        return decorate(func)
    return decorate
