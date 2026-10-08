"""
Core Tool Registry & Dispatch Engine for Voice-RAG Bot.

Provides:
- Central TOOL_REGISTRY dictionary
- @register_tool decorator
- call_tool execution helper
- LangChain StructuredTool conversion
- Composio ecosystem tool loader
"""

import inspect
import logging
import os
from typing import Callable, Dict, Any, List, Optional

# Optional LangChain integration
try:
    from langchain_core.tools import StructuredTool, BaseTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    BaseTool = Any

# Optional Composio integration
try:
    from composio import Composio
    from composio_langchain import LangchainProvider
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False

logger = logging.getLogger("voicerag.tools.base")

# Global Master Tool Registry: {name: {name, description, func, parameters, param_names}}
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_tool(name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
    """
    Decorator to register a function as a tool in the central TOOL_REGISTRY.
    """
    def decorator(func: Callable):
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description.strip(),
            "func": func,
            "parameters": parameters or {"type": "object", "properties": {p: {"type": "string"} for p in param_names}},
            "param_names": param_names,
        }
        logger.info(f"Registered tool: '{name}'")
        return func
    return decorator


def register_external_tool(name: str, func: Callable, description: str, parameters: Optional[Dict[str, Any]] = None):
    """
    Programmatically registers an imported Python function into the registry.
    """
    return register_tool(name=name, description=description, parameters=parameters)(func)


def register_langchain_tool(lc_tool: Any):
    """
    Registers a native LangChain BaseTool into the central registry.
    """
    if not hasattr(lc_tool, "name") or not hasattr(lc_tool, "invoke"):
        raise ValueError("Object is not a valid LangChain Tool.")
    
    def wrapped_func(**kwargs):
        return lc_tool.invoke(kwargs)
    
    return register_tool(
        name=lc_tool.name,
        description=getattr(lc_tool, "description", "LangChain Tool"),
    )(wrapped_func)


def call_tool(tool_name: str, **kwargs) -> Any:
    """
    Executes a registered tool dynamically by name with provided keyword arguments.
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


def get_langchain_tools() -> List[Any]:
    """
    Converts all registered tools into native LangChain StructuredTools.
    Allows using this entire toolset inside any LangChain Agent, LCEL Chain, or LangGraph.
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError("langchain-core is required to export LangChain tools. Run: pip install langchain-core")

    lc_tools = []
    for name, entry in TOOL_REGISTRY.items():
        try:
            lc_t = StructuredTool.from_function(
                func=entry["func"],
                name=name,
                description=entry["description"],
            )
            lc_tools.append(lc_t)
        except Exception as e:
            logger.debug(f"Could not convert tool '{name}' to LangChain: {e}")
    return lc_tools


def load_composio_tools(
    api_key: Optional[str] = None,
    toolkits: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    user_id: str = "default",
) -> List[str]:
    """
    Loads pre-built enterprise tools from Composio (e.g. Gmail, Google Sheets, Slack, Jira, GitHub)
    and registers them into the central Voice-RAG TOOL_REGISTRY.
    """
    if not COMPOSIO_AVAILABLE:
        raise ImportError(
            "composio-core and composio-langchain are required. Run: pip install composio-core composio-langchain"
        )

    key = api_key or os.getenv("COMPOSIO_API_KEY")
    if not key:
        logger.warning("No COMPOSIO_API_KEY provided or found in environment. Set COMPOSIO_API_KEY to load Composio tools.")
        return []

    try:
        provider = LangchainProvider()
        c = Composio(api_key=key, provider=provider)
        fetch_kwargs: Dict[str, Any] = {"user_id": user_id}
        if toolkits:
            fetch_kwargs["toolkits"] = toolkits
        if tools:
            fetch_kwargs["tools"] = tools

        lc_tools = c.tools.get(**fetch_kwargs)
        registered_names: List[str] = []
        for t in lc_tools:
            register_langchain_tool(t)
            registered_names.append(t.name)

        logger.info(f"Loaded and registered {len(registered_names)} Composio tools into registry: {registered_names}")
        return registered_names
    except Exception as e:
        logger.error(f"Error loading Composio tools: {e}")
        return []
