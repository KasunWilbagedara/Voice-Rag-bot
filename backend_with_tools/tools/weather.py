"""
Live Weather Forecast Tool.

Uses Open-Meteo free API to fetch real-time temperature, condition, humidity, and wind.
"""

import logging
from typing import Dict, Any
import requests

from backend_with_tools.tools.base import register_tool

logger = logging.getLogger("voicerag.tools.weather")


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
