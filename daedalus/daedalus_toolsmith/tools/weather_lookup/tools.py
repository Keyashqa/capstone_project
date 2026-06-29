from typing import Dict, Any

from daedalus_toolsmith.tools.registry.tools import tool_registry

FAKE_WEATHER: Dict[str, Dict[str, object]] = {
    "LONDON": {"city": "London", "temp_c": 12, "condition": "Cloudy"},
    "VIENNA": {"city": "Vienna", "temp_c": 8, "condition": "Rain"},
    "SEOUL": {"city": "Seoul", "temp_c": 6, "condition": "Clear"},
    "NEW YORK": {"city": "New York", "temp_c": 5, "condition": "Snow"},
}


def get_weather(city: str) -> Dict[str, Any]:
    """
    Look up deterministic weather for a given city in the sandbox dataset.

    Args:
        city: City name (case-insensitive), e.g., "Vienna", "LONDON".

    Returns:
        dict on success:
            {
                "status": "success",
                "city": str,
                "temp_c": int | float,
                "condition": str,
            }
        dict on error:
            {
                "status": "error",
                "error_message": "...",
            }
    """
    if not isinstance(city, str) or not city.strip():
        return {
            "status": "error",
            "error_message": "city must be a non-empty string",
        }

    key = city.strip().upper()
    info = FAKE_WEATHER.get(key)
    if info is None:
        return {
            "status": "error",
            "error_message": f"City '{city}' is not in the sandbox weather dataset.",
        }

    return {
        "status": "success",
        "city": info["city"],
        "temp_c": info["temp_c"],
        "condition": info["condition"],
    }


def list_supported_cities() -> Dict[str, Any]:
    """
    List all cities available in the sandbox weather dataset.

    Returns:
        dict:
            {
                "status": "success",
                "cities": ["London", "Vienna", ...],
                "count": int
            }
    """
    cities = [info["city"] for info in FAKE_WEATHER.values()]
    return {
        "status": "success",
        "cities": cities,
        "count": len(cities),
    }


def register_weather_tools() -> None:
    """
    Register native weather tools into the InMemoryToolRegistry.
    This function is called at import time.
    """
    tool_registry.register(
        name="get_weather",
        func=get_weather,
        description="Return weather information (temperature and condition) for a given city.",
        tags=["native", "weather"],
    )

    tool_registry.register(
        name="list_supported_cities",
        func=list_supported_cities,
        description="List all cities for which weather information is available.",
        tags=["native", "weather"],
    )
