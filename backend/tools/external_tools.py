"""
tools/external_tools.py — Real-Time External & Public Tools
=============================================================
Registers four real-time tools into the central TOOL_REGISTRY:
  - get_live_weather      — Open-Meteo geocoding + weather API
  - web_search            — DuckDuckGo Instant Answer + Wikipedia fallback
  - get_current_datetime  — System clock (Asia/Colombo default)
  - calculate_expression  — Safe AST-based math evaluator
"""

import ast
import logging
import operator
import re
from datetime import datetime
from typing import Any, Dict

import requests

from backend.tools.registry import register_tool

logger = logging.getLogger("voicerag.tools.external")


# ---------------------------------------------------------------------------
# 1. Live Weather
# ---------------------------------------------------------------------------

@register_tool(
    name="get_live_weather",
    description=(
        "Gets real-time weather, temperature (Celsius), humidity, and wind conditions "
        "for any city (e.g. Colombo, Kandy, Galle, London, Tokyo)."
    ),
)
def get_live_weather(city: str) -> Dict[str, Any]:
    """Fetches real-time weather data for a given city using Open-Meteo free API."""
    clean_city = city.strip().strip("'\"")
    if not clean_city:
        return {"error": "City name is required."}

    try:
        # Geocode city → lat/lon
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1"
        geo_res = requests.get(geo_url, timeout=4).json()
        results = geo_res.get("results")
        if not results:
            return {"city": clean_city, "status": "not_found", "message": f"Could not find coordinates for city '{clean_city}'."}

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        country = place.get("country", "")

        # Fetch live weather
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_res = requests.get(w_url, timeout=4).json()
        cw = w_res.get("current_weather", {})

        weather_code = cw.get("weathercode", 0)
        conditions_map = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 51: "Light drizzle", 61: "Slight rain", 63: "Moderate rain",
            65: "Heavy rain", 80: "Rain showers", 95: "Thunderstorm",
        }
        condition = conditions_map.get(weather_code, "Partly cloudy")

        return {
            "city": place["name"],
            "country": country,
            "temperature_celsius": cw.get("temperature"),
            "condition": condition,
            "windspeed_kmh": cw.get("windspeed"),
            "observation_time": cw.get("time"),
            "status": "success",
        }
    except Exception as e:
        logger.warning(f"Weather tool error for '{clean_city}': {e}")
        return {"city": clean_city, "status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 2. Web Search (DuckDuckGo + Wikipedia fallback)
# ---------------------------------------------------------------------------

@register_tool(
    name="web_search",
    description=(
        "Live web search to find current information, facts, company profiles, "
        "news, and definitions from DuckDuckGo and Wikipedia."
    ),
)
def web_search(query: str) -> Dict[str, Any]:
    """Live web search using DuckDuckGo Instant Answer and Wikipedia REST API."""
    clean_q = query.strip()
    if not clean_q:
        return {"error": "Search query is required."}

    # 1. DuckDuckGo Instant Answer
    try:
        ddg_url = (
            f"https://api.duckduckgo.com/?q={requests.utils.quote(clean_q)}"
            "&format=json&no_html=1&skip_disambig=1"
        )
        ddg_res = requests.get(ddg_url, timeout=4).json()
        abstract = ddg_res.get("AbstractText")
        source_url = ddg_res.get("AbstractURL")
        heading = ddg_res.get("Heading")
        if abstract:
            return {
                "query": clean_q,
                "title": heading or clean_q,
                "summary": abstract,
                "source": source_url or "DuckDuckGo",
                "status": "success",
            }
    except Exception as ddg_err:
        logger.debug(f"DuckDuckGo search note: {ddg_err}")

    # 2. Wikipedia Summary API fallback
    try:
        wiki_title = re.sub(r"[^a-zA-Z0-9_\s]", "", clean_q).strip().replace(" ", "_")
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"
        wiki_res = requests.get(wiki_url, headers={"User-Agent": "VoiceRagBot/1.0"}, timeout=4).json()
        extract = wiki_res.get("extract")
        if extract:
            return {
                "query": clean_q,
                "title": wiki_res.get("title", clean_q),
                "summary": extract,
                "source": wiki_res.get("content_urls", {}).get("desktop", {}).get("page", "Wikipedia"),
                "status": "success",
            }
    except Exception as wiki_err:
        logger.debug(f"Wikipedia search note: {wiki_err}")

    return {
        "query": clean_q,
        "summary": f"No instant public web summary found for '{clean_q}'.",
        "status": "no_results",
    }


# ---------------------------------------------------------------------------
# 3. Current Date & Time
# ---------------------------------------------------------------------------

@register_tool(
    name="get_current_datetime",
    description=(
        "Returns current date, local time, day of the week, and timezone information "
        "(defaults to Sri Lanka / Asia/Colombo)."
    ),
)
def get_current_datetime(timezone_str: str = "Asia/Colombo") -> Dict[str, Any]:
    """Returns exact current date and time."""
    now = datetime.now()
    return {
        "datetime_iso": now.isoformat(),
        "readable_date": now.strftime("%A, %B %d, %Y"),
        "readable_time": now.strftime("%I:%M:%S %p"),
        "day_of_week": now.strftime("%A"),
        "year": now.year,
        "month": now.strftime("%B"),
        "day": now.day,
        "timezone": timezone_str,
        "status": "success",
    }


# ---------------------------------------------------------------------------
# 4. Safe Math Calculator
# ---------------------------------------------------------------------------

@register_tool(
    name="calculate_expression",
    description=(
        "Evaluates mathematical, statistical, or financial calculations safely "
        "without LLM arithmetic errors (e.g. '45000 * 0.15', '(120 + 45) / 2')."
    ),
)
def calculate_expression(expression: str) -> Dict[str, Any]:
    """Safely evaluates a math expression using Python AST (no eval())."""
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Constants must be numeric")
        elif isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in allowed_operators:
                raise ValueError(f"Operator {op.__name__} not permitted.")
            return allowed_operators[op](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op not in allowed_operators:
                raise ValueError(f"Unary operator {op.__name__} not permitted.")
            return allowed_operators[op](_eval(node.operand))
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")

    try:
        clean_expr = expression.replace(",", "").strip()
        tree = ast.parse(clean_expr, mode="eval")
        result = _eval(tree.body)
        return {
            "expression": expression,
            "result": round(result, 4) if isinstance(result, float) else result,
            "status": "success",
        }
    except Exception as e:
        return {"expression": expression, "error": str(e), "status": "failed"}
