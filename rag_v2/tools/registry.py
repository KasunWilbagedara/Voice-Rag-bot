"""
rag_v2/tools/registry.py
-------------------------
Central tool registry for the RAG v2 agent.  Tools are registered via the
``@register_tool`` decorator and can be invoked by name through ``call_tool``.
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("rag_v2.tools.registry")

# ── Global registry ──────────────────────────────────────────────────────────
TOOL_REGISTRY: Dict[str, Dict] = {}


def register_tool(
    name: str,
    description: str,
    parameters: Optional[Dict] = None,
) -> Callable:
    """Decorator factory that registers a function as a named tool.

    Usage
    -----
    >>> @register_tool(
    ...     name="my_tool",
    ...     description="Does something useful",
    ...     parameters={"query": {"type": "string", "description": "..."}},
    ... )
    ... def my_tool(query: str) -> str:
    ...     return query.upper()

    Parameters
    ----------
    name:
        Unique tool identifier used when calling ``call_tool``.
    description:
        Human-readable description exposed to the LLM.
    parameters:
        Optional JSON-Schema-like dict describing accepted parameters.
        When ``None`` the decorator introspects the function signature and
        builds a minimal schema automatically.

    Returns
    -------
    Callable
        The original function, unchanged.
    """

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        param_names: List[str] = [
            p for p in sig.parameters if p != "self"
        ]

        # Build a minimal parameter schema from type annotations when the
        # caller did not supply one explicitly.
        resolved_parameters: Dict = parameters or {}
        if not resolved_parameters:
            type_map = {
                int: "integer",
                float: "number",
                bool: "boolean",
                str: "string",
                list: "array",
                dict: "object",
            }
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                annotation = param.annotation
                py_type = annotation if annotation is not inspect.Parameter.empty else str
                json_type = type_map.get(py_type, "string")
                entry: Dict[str, Any] = {"type": json_type}
                if param.default is not inspect.Parameter.empty:
                    entry["default"] = param.default
                resolved_parameters[param_name] = entry

        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "func": func,
            "parameters": resolved_parameters,
            "param_names": param_names,
        }

        logger.info("Registered tool: '%s' (params: %s)", name, param_names)
        return func

    return decorator


def call_tool(tool_name: str, **kwargs: Any) -> Any:
    """Call a registered tool by name.

    Parameters
    ----------
    tool_name:
        The name used when the tool was registered.
    **kwargs:
        Keyword arguments forwarded directly to the tool function.

    Returns
    -------
    Any
        Whatever the tool function returns.

    Raises
    ------
    ValueError
        If *tool_name* is not in the registry.
    """
    if tool_name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        raise ValueError(
            f"Tool '{tool_name}' not found. "
            f"Available tools: {available}"
        )

    entry = TOOL_REGISTRY[tool_name]
    func: Callable = entry["func"]

    logger.debug("Calling tool '%s' with kwargs: %s", tool_name, list(kwargs.keys()))
    result = func(**kwargs)
    logger.debug("Tool '%s' returned successfully.", tool_name)
    return result


def list_tools() -> List[Dict]:
    """Return metadata for all registered tools (excluding the callable).

    Returns
    -------
    List[Dict]
        Each dict has keys: ``name``, ``description``, ``parameters``.
    """
    return [
        {
            "name": entry["name"],
            "description": entry["description"],
            "parameters": entry["parameters"],
        }
        for entry in TOOL_REGISTRY.values()
    ]
