"""
rag_v2/tools/external.py
-------------------------
Live external data tools registered in TOOL_REGISTRY.

Tools
-----
- get_live_weather    – Open-Meteo weather API (no API key required)
- web_search          – DuckDuckGo Instant Answer API
- calculate_expression – Safe AST-based math evaluator
- get_current_datetime – UTC datetime snapshot
"""

import ast
import logging
import math
import operator
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from rag_v2.tools.registry import register_tool

logger = logging.getLogger("rag_v2.tools.external")

# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_live_weather
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    name="get_live_weather",
    description=(
        "Get the current weather for a given city using the Open-Meteo API. "
        "Returns temperature (°C), wind speed, and weather condition code. "
        "No API key is required."
    ),
    parameters={
        "city": {
            "type": "string",
            "description": "The name of the city to fetch weather for (e.g. 'London').",
        }
    },
)
def get_live_weather(city: str) -> Dict:
    """Fetch current weather for *city* via Open-Meteo."""
    try:
        # ── Geocoding ────────────────────────────────────────────────────────
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        )
        geo_resp = requests.get(geo_url, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        results = geo_data.get("results")
        if not results:
            return {"error": f"City '{city}' not found in geocoding database."}

        location = results[0]
        lat: float = location["latitude"]
        lon: float = location["longitude"]
        resolved_name: str = location.get("name", city)
        country: str = location.get("country", "")

        # ── Weather ──────────────────────────────────────────────────────────
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )
        weather_resp = requests.get(weather_url, timeout=10)
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

        cw = weather_data.get("current_weather", {})

        logger.info(
            "Weather for '%s' (%s, %s): %s°C, wind %s km/h",
            resolved_name,
            lat,
            lon,
            cw.get("temperature"),
            cw.get("windspeed"),
        )

        return {
            "city": f"{resolved_name}, {country}".strip(", "),
            "latitude": lat,
            "longitude": lon,
            "temperature": cw.get("temperature"),
            "windspeed": cw.get("windspeed"),
            "weathercode": cw.get("weathercode"),
            "is_day": bool(cw.get("is_day", 1)),
            "unit": "Celsius",
        }

    except requests.RequestException as exc:
        logger.error("Weather API request failed for city '%s': %s", city, exc)
        return {"error": f"Network error fetching weather for '{city}': {exc}"}
    except Exception as exc:
        logger.error("Unexpected error in get_live_weather for '%s': %s", city, exc)
        return {"error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: web_search
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    name="web_search",
    description=(
        "Search the web using the DuckDuckGo Instant Answer API and return a "
        "list of relevant results. Each result includes a title, URL, and snippet."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "The search query string.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default 5).",
            "default": 5,
        },
    },
)
def web_search(query: str, max_results: int = 5) -> List[Dict]:
    """Search DuckDuckGo and return structured results."""
    try:
        ddg_url = (
            f"https://api.duckduckgo.com/"
            f"?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(ddg_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results: List[Dict] = []

        # Abstract (top answer)
        if data.get("AbstractText") and data.get("AbstractURL"):
            results.append(
                {
                    "title": data.get("Heading", query),
                    "url": data["AbstractURL"],
                    "snippet": data["AbstractText"],
                }
            )

        # Related topics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            # Some topics are grouped; handle both shapes
            if "Topics" in topic:
                for sub in topic["Topics"]:
                    if len(results) >= max_results:
                        break
                    if sub.get("FirstURL") and sub.get("Text"):
                        results.append(
                            {
                                "title": sub.get("Text", "")[:80],
                                "url": sub["FirstURL"],
                                "snippet": sub.get("Text", ""),
                            }
                        )
            elif topic.get("FirstURL") and topic.get("Text"):
                results.append(
                    {
                        "title": topic.get("Text", "")[:80],
                        "url": topic["FirstURL"],
                        "snippet": topic.get("Text", ""),
                    }
                )

        if not results:
            logger.info("DuckDuckGo returned no results for query: '%s'", query)
            return [
                {
                    "title": "No results found",
                    "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                    "snippet": (
                        f"DuckDuckGo Instant Answer API returned no structured results "
                        f"for '{query}'. Try opening the URL directly."
                    ),
                }
            ]

        logger.info("web_search('%s') → %d results", query, len(results))
        return results[:max_results]

    except requests.RequestException as exc:
        logger.error("web_search network error for '%s': %s", query, exc)
        return [{"error": f"Network error: {exc}"}]
    except Exception as exc:
        logger.error("web_search unexpected error for '%s': %s", query, exc)
        return [{"error": str(exc)}]


# ─────────────────────────────────────────────────────────────────────────────
# Tool: calculate_expression
# ─────────────────────────────────────────────────────────────────────────────

# Safe node types allowed in the AST
_SAFE_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.UAdd,
    ast.USub,
    ast.Call,
    ast.Name,
    ast.Load,
}

# Allowed math function names
_SAFE_NAMES: Dict[str, Any] = {
    name: getattr(math, name)
    for name in dir(math)
    if not name.startswith("_")
}
_SAFE_NAMES.update(
    {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "int": int,
        "float": float,
    }
)

# Operator mapping for eval
_OPS: Dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval_node(node: ast.AST) -> Any:
    """Recursively evaluate a safe AST node."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval_node(node.operand)
        return _OPS[op_type](operand)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed.")
        func_name = node.func.id
        if func_name not in _SAFE_NAMES:
            raise ValueError(f"Function '{func_name}' is not allowed.")
        func = _SAFE_NAMES[func_name]
        args = [_safe_eval_node(arg) for arg in node.args]
        return func(*args)
    if isinstance(node, ast.Name):
        # Allow math constants (pi, e, inf, nan, tau)
        if node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        raise ValueError(f"Name '{node.id}' is not allowed.")
    raise ValueError(f"Unsupported AST node type: {type(node).__name__}")


@register_tool(
    name="calculate_expression",
    description=(
        "Safely evaluate a mathematical expression and return the result. "
        "Supports arithmetic operators (+, -, *, /, **, %, //), parentheses, "
        "and common math functions (sqrt, log, sin, cos, tan, abs, round, etc.). "
        "Does NOT use Python's eval(); uses a restricted AST evaluator instead."
    ),
    parameters={
        "expression": {
            "type": "string",
            "description": (
                "The mathematical expression to evaluate (e.g. '2 ** 10', 'sqrt(144)', "
                "'sin(pi / 2)')."
            ),
        }
    },
)
def calculate_expression(expression: str) -> Dict:
    """Evaluate *expression* safely using a restricted AST walker."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        # Validate all nodes are safe
        for node in ast.walk(tree):
            if type(node) not in _SAFE_NODES:
                raise ValueError(f"Disallowed AST node '{type(node).__name__}' in expression.")

        result = _safe_eval_node(tree)

        # Keep the result JSON-serialisable
        if isinstance(result, complex):
            result_str = str(result)
            logger.info("calculate_expression('%s') = %s (complex)", expression, result_str)
            return {"expression": expression, "result": result_str}

        logger.info("calculate_expression('%s') = %s", expression, result)
        return {"expression": expression, "result": result}

    except ZeroDivisionError:
        return {"expression": expression, "error": "Division by zero."}
    except (ValueError, TypeError, SyntaxError) as exc:
        logger.warning("calculate_expression error for '%s': %s", expression, exc)
        return {"expression": expression, "error": str(exc)}
    except Exception as exc:
        logger.error("Unexpected error in calculate_expression('%s'): %s", expression, exc)
        return {"expression": expression, "error": f"Unexpected error: {exc}"}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_current_datetime
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    name="get_current_datetime",
    description=(
        "Return the current date and time in UTC. Useful for time-sensitive "
        "queries or whenever the assistant needs to know what time it is."
    ),
    parameters={},
)
def get_current_datetime() -> Dict:
    """Return a snapshot of the current UTC datetime."""
    now = datetime.now(tz=timezone.utc)
    result = {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": "UTC",
        "unix_timestamp": int(now.timestamp()),
    }
    logger.info("get_current_datetime() → %s", result["datetime"])
    return result
