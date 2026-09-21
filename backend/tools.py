"""
Central Tool Registry for Voice-RAG Bot.

A unified, hybrid tool architecture supporting:
1. Native ultra-low-latency direct dispatch (for high-speed voice responses < 1s).
2. LangChain compatibility (every tool is convertible to a LangChain StructuredTool/BaseTool).
3. Real-world tools: Live Weather, Web Search, Order/Ticket Tracking, Math Calculator,
   Real-Time DateTime, Student Lookup, Safe Multi-DB SQL, and RAG Vector Retrieval.

To add a new tool in the future:
    @register_tool(name="my_tool", description="Tool explanation")
    def my_tool(arg1: str) -> dict:
        return {"data": arg1}

Or register any LangChain tool directly:
    register_langchain_tool(my_langchain_tool)
"""

import ast
import inspect
import logging
import operator
import re
import os
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional
import requests

from backend import db_query_service
from backend.db import get_user_memories, save_or_update_memory

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

logger = logging.getLogger("voicerag.tools")

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


# =====================================================================
# 1. REAL-TIME EXTERNAL & PUBLIC TOOLS
# =====================================================================

@register_tool(
    name="get_live_weather",
    description="Gets real-time weather, temperature (Celsius), humidity, and wind conditions for any city (e.g. Colombo, Kandy, Galle, London, Tokyo).",
)
def get_live_weather(city: str) -> Dict[str, Any]:
    """Fetches real-time weather data for a given city using Open-Meteo free API."""
    clean_city = city.strip().strip("'\"")
    if not clean_city:
        return {"error": "City name is required."}

    try:
        # 1. Geocode city name to lat/lon
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1"
        geo_res = requests.get(geo_url, timeout=4).json()
        results = geo_res.get("results")
        if not results:
            return {"city": clean_city, "status": "not_found", "message": f"Could not find coordinates for city '{clean_city}'."}

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        country = place.get("country", "")

        # 2. Fetch live weather
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_res = requests.get(w_url, timeout=4).json()
        cw = w_res.get("current_weather", {})

        weather_code = cw.get("weathercode", 0)
        # Interpret standard WMO weather codes
        conditions_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            51: "Light drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            80: "Rain showers",
            95: "Thunderstorm",
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


@register_tool(
    name="web_search",
    description="Live web search to find current information, facts, company profiles, news, and definitions from DuckDuckGo and Wikipedia.",
)
def web_search(query: str) -> Dict[str, Any]:
    """Live web search using DuckDuckGo Instant Answer and Wikipedia REST API."""
    clean_q = query.strip()
    if not clean_q:
        return {"error": "Search query is required."}

    # 1. DuckDuckGo Instant Answer
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={requests.utils.quote(clean_q)}&format=json&no_html=1&skip_disambig=1"
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

    # 2. Wikipedia Summary API
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


@register_tool(
    name="get_current_datetime",
    description="Returns current date, local time, day of the week, and timezone information (defaults to Sri Lanka / Asia/Colombo).",
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


@register_tool(
    name="calculate_expression",
    description="Evaluates mathematical, statistical, or financial calculations safely without LLM arithmetic errors (e.g. '45000 * 0.15', '(120 + 45) / 2').",
)
def calculate_expression(expression: str) -> Dict[str, Any]:
    """Safely evaluates a math expression using Python AST."""
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


# =====================================================================
# 2. CUSTOMER ORDERS & SUPPORT TICKET TRACKING TOOLS
# =====================================================================

@register_tool(
    name="track_customer_order",
    description="Tracks an order by Order ID (e.g. ORD-9021). Returns customer ID, product, amount, status, and order date.",
)
def track_customer_order(order_id: str) -> Dict[str, Any]:
    """Look up order details by order ID."""
    clean_id = order_id.upper().strip()
    match = re.search(r"\b(ORD-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM orders WHERE UPPER(order_id) = '{target_id}' OR order_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_query_service.db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"order": res["rows"][0], "status": "found"}
    return {"order_id": target_id, "status": "not_found", "message": f"No order found with ID {target_id}"}


@register_tool(
    name="track_support_ticket",
    description="Tracks a customer support ticket by Ticket ID (e.g. TCK-5501). Returns customer name, issue category, description, and status.",
)
def track_support_ticket(ticket_id: str) -> Dict[str, Any]:
    """Look up ticket details by ticket ID."""
    clean_id = ticket_id.upper().strip()
    match = re.search(r"\b(TCK-\d{3,8})\b", clean_id)
    target_id = match.group(1) if match else clean_id

    sql = f"SELECT * FROM support_tickets WHERE UPPER(ticket_id) = '{target_id}' OR ticket_id LIKE '%{target_id}%' LIMIT 1;"
    res = db_query_service.db_manager.execute_safe_sql(sql, db_id="customer_support_db")
    if res.get("rows"):
        return {"ticket": res["rows"][0], "status": "found"}
    return {"ticket_id": target_id, "status": "not_found", "message": f"No support ticket found with ID {target_id}"}


# =====================================================================
# 3. DATABASE, STUDENT & USER MEMORY TOOLS
# =====================================================================

@register_tool(
    name="lookup_student",
    description="Finds student academic profile, GPA, enrollment year, and status by student ID (e.g. STU1042) or student name.",
)
def lookup_student(search_term: str) -> Optional[Dict[str, Any]]:
    """Lookup a student record from PostgreSQL or in-memory student database."""
    return db_query_service.query_student_by_id_or_name(search_term)


@register_tool(
    name="execute_sql",
    description="Executes a safe read-only SQL SELECT query against a connected database (customer_support_db, primary_db).",
)
def execute_sql(sql_query: str, db_id: Optional[str] = "customer_support_db") -> Dict[str, Any]:
    """Runs a read-only SQL query against the target database."""
    return db_query_service.db_manager.execute_safe_sql(sql_query=sql_query, db_id=db_id)


@register_tool(
    name="list_databases",
    description="Returns all active database connections, table counts, and registered dataset tables.",
)
def list_databases() -> List[Dict[str, Any]]:
    """Lists all connected databases and their table lists."""
    return db_query_service.db_manager.list_databases()


@register_tool(
    name="get_database_schema",
    description="Returns the column names and data types for all tables in a specific database ID.",
)
def get_database_schema(db_id: str = "customer_support_db") -> List[Dict[str, Any]]:
    """Inspects the schema of a database."""
    return db_query_service.db_manager.get_database_schema(db_id)


@register_tool(
    name="get_session_memories",
    description="Retrieves all persistent remembered facts, identities, and entities stored for a user session.",
)
def get_session_memories(session_id: str = "default_user") -> List[Dict[str, Any]]:
    """Fetches user memories for the given session ID."""
    return get_user_memories(session_id)


@register_tool(
    name="save_session_memory",
    description="Saves or updates a persistent user fact, entity, or preference (e.g., user_name, last_tracked_order).",
)
def save_session_memory(session_id: str, key: str, value: str, category: str = "general") -> bool:
    """Stores a fact into persistent memory."""
    try:
        save_or_update_memory(session_id=session_id, key=key, value=value, category=category)
        return True
    except Exception as e:
        logger.warning(f"Failed to save session memory: {e}")
        return False


@register_tool(
    name="search_knowledge_base",
    description="Performs cross-lingual hybrid (Dense Vector + BM25 Lexical) search over ingested document chunks.",
)
def search_knowledge_base(
    query_text: str,
    top_k: int = 8,
    custom_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Searches vector & keyword database using query text."""
    from backend.rag_service import get_embedding, search_vector_database
    query_embedding = get_embedding(query_text, custom_api_key=custom_api_key)
    return search_vector_database(
        query_embedding=query_embedding,
        top_k=top_k,
        query_text=query_text,
        custom_api_key=custom_api_key,
    )


# =====================================================================
# 4. HYBRID LANGCHAIN EXPORT & DISPATCHER HELPERS
# =====================================================================

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


# =====================================================================
# 5. COMPOSIO PRE-BUILT TOOLSET INTEGRATION
# =====================================================================

def load_composio_tools(
    api_key: Optional[str] = None,
    toolkits: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    user_id: str = "default",
) -> List[str]:
    """
    Loads pre-built enterprise tools from Composio (e.g. Gmail, Google Sheets, Slack, Jira, GitHub)
    and registers them into the central Voice-RAG TOOL_REGISTRY.

    Example:
        # Load Gmail and Slack tools
        loaded_tools = load_composio_tools(toolkits=["gmail", "slack"])
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
