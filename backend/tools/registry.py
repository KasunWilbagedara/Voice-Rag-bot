"""
tools/registry.py — Master Tool Registry & Dispatcher
=======================================================
Provides the central ``TOOL_REGISTRY`` dict, the ``@register_tool`` decorator,
``register_external_tool()``, ``register_langchain_tool()``, and the
``call_tool()`` dispatcher.

All tool definitions in the other sub-modules import and use
``@register_tool`` from here, so there is one single registry shared across
the entire process.
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("voicerag.tools.registry")

# ---------------------------------------------------------------------------
# Global master registry
# ---------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_tool(name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
    """
    Decorator that registers a function as a tool in ``TOOL_REGISTRY``.

    Usage::

        @register_tool(name="my_tool", description="Does something useful.")
        def my_tool(arg1: str) -> dict:
            return {"data": arg1}

    Args:
        name:        Unique tool identifier.
        description: Human-readable description surfaced to the LLM.
        parameters:  Optional JSON-Schema ``properties`` dict.  Auto-inferred
                     from the function signature when omitted.

    Returns:
        The original function (unmodified) after registering it.
    """
    def decorator(func: Callable):
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description.strip(),
            "func": func,
            "parameters": parameters or {
                "type": "object",
                "properties": {p: {"type": "string"} for p in param_names},
            },
            "param_names": param_names,
        }
        logger.info(f"Registered tool: '{name}'")
        return func

    return decorator


def register_external_tool(
    name: str,
    func: Callable,
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
):
    """
    Programmatically registers an imported Python function into the registry.

    Equivalent to applying ``@register_tool`` after the fact.
    """
    return register_tool(name=name, description=description, parameters=parameters)(func)


def register_langchain_tool(lc_tool: Any):
    """
    Wraps a native LangChain ``BaseTool`` and registers it in the central registry.

    Args:
        lc_tool: Any object that exposes ``.name`` and ``.invoke()``.

    Raises:
        ValueError: If *lc_tool* does not look like a LangChain tool.
    """
    if not hasattr(lc_tool, "name") or not hasattr(lc_tool, "invoke"):
        raise ValueError("Object is not a valid LangChain Tool.")

    def wrapped_func(**kwargs):
        return lc_tool.invoke(kwargs)

    return register_tool(
        name=lc_tool.name,
        description=getattr(lc_tool, "description", "LangChain Tool"),
    )(wrapped_func)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def call_tool(tool_name: str, **kwargs) -> Any:
    """
    Executes a registered tool dynamically by name with provided keyword arguments.

    Args:
        tool_name: Key in ``TOOL_REGISTRY``.
        **kwargs:  Arguments forwarded verbatim to the tool function.

    Returns:
        The tool's return value.

    Raises:
        ValueError:  If *tool_name* is not registered.
        TypeError:   If wrong arguments are provided.
        Exception:   Any exception raised by the tool function itself.
    """
    tool_entry = TOOL_REGISTRY.get(tool_name)
    if not tool_entry:
        available = ", ".join(TOOL_REGISTRY.keys())
        raise ValueError(f"Tool '{tool_name}' not found. Available tools: [{available}]")

    func = tool_entry["func"]
    try:
        return func(**kwargs)
    except TypeError as te:
        logger.error(f"Invalid arguments for tool '{tool_name}': {te}")
        raise
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        raise


def list_tools() -> List[Dict[str, Any]]:
    """
    Returns metadata for all registered tools (name, description, parameters).

    Returns:
        List of dicts — one per registered tool.
    """
    return [
        {
            "name": data["name"],
            "description": data["description"],
            "parameters": data["parameters"],
            "param_names": data["param_names"],
        }
        for data in TOOL_REGISTRY.values()
    ]
