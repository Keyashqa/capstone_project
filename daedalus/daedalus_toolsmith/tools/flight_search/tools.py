from typing import Dict, Any

from daedalus_toolsmith.tools.registry.tools import tool_registry

# Deterministic flight dataset
FLIGHTS_DATA: list[dict[str, object]] = [
    {
        "flight_id": "OS451",
        "from_airport": "VIE",
        "to_airport": "LHR",
        "date": "2025-12-20",
        "price_eur": 180.0,
        "duration_min": 145,
        "airline": "Austrian Airlines",
    },
    {
        "flight_id": "BA703",
        "from_airport": "VIE",
        "to_airport": "LHR",
        "date": "2025-12-20",
        "price_eur": 210.0,
        "duration_min": 150,
        "airline": "British Airways",
    },
    {
        "flight_id": "LH1245",
        "from_airport": "VIE",
        "to_airport": "FRA",
        "date": "2025-12-20",
        "price_eur": 120.0,
        "duration_min": 75,
        "airline": "Lufthansa",
    },
    {
        "flight_id": "OS452",
        "from_airport": "LHR",
        "to_airport": "VIE",
        "date": "2025-12-27",
        "price_eur": 190.0,
        "duration_min": 155,
        "airline": "Austrian Airlines",
    },
    {
        "flight_id": "KE937",
        "from_airport": "ICN",
        "to_airport": "VIE",
        "date": "2025-12-21",
        "price_eur": 650.0,
        "duration_min": 720,
        "airline": "Korean Air",
    },
]


def list_all_flights() -> Dict[str, Any]:
    """
    Return all flights in the deterministic sandbox dataset.

    Returns:
        dict: {
            "status": "success",
            "flights": [...],  # list of flight dicts
            "count": int
        }
    """
    return {
        "status": "success",
        "flights": FLIGHTS_DATA,
        "count": len(FLIGHTS_DATA),
    }


def search_flights(
        from_airport: str | None = None,
        to_airport: str | None = None,
        date: str | None = None,
        max_price_eur: float | None = None,
) -> Dict[str, Any]:
    """
    Search flights in the sandbox dataset with simple filters.

    Args:
        from_airport: IATA code of departure airport (e.g., "VIE"), optional.
        to_airport: IATA code of arrival airport (e.g., "LHR"), optional.
        date: Flight date in ISO format "YYYY-MM-DD", optional.
        max_price_eur: Maximum price in EUR, optional.

    Returns:
        dict:
            - status: "success"
            - flights: list of matching flight dicts
            - count: number of flights
    """

    def norm(code: str | None) -> str | None:
        return code.strip().upper() if isinstance(code, str) else None

    from_norm = norm(from_airport)
    to_norm = norm(to_airport)
    date_norm = date.strip() if isinstance(date, str) else None

    results: list[dict[str, object]] = []
    for f in FLIGHTS_DATA:
        if from_norm and f["from_airport"] != from_norm:
            continue
        if to_norm and f["to_airport"] != to_norm:
            continue
        if date_norm and f["date"] != date_norm:
            continue
        if max_price_eur is not None and float(f["price_eur"]) > float(max_price_eur):
            continue
        results.append(f)

    return {
        "status": "success",
        "flights": results,
        "count": len(results),
    }


def register_flight_tools() -> None:
    """
    Register native flight tools into the tool registry.
    """
    tool_registry.register(
        name="list_all_flights",
        func=list_all_flights,
        description="Return all available flights with their attributes.",
        tags=["native", "flight"],
    )

    tool_registry.register(
        name="search_flights",
        func=search_flights,
        description=(
            "Search flights with optional filters such as from_airport, "
            "to_airport, date (YYYY-MM-DD), and max_price_eur. Returns matching flights."
        ),
        tags=["native", "flight"],
    )
