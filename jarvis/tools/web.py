"""Weather (Open-Meteo: free, no API key). Web search is Claude's built-in
server-side tool and is declared in brain.py, not here."""

from __future__ import annotations

import httpx

from jarvis.tools import Context, ToolError, tool

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}


def geocode(location: str) -> dict:
    name, _, hint = location.partition(",")
    resp = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": name.strip(), "count": 10, "language": "en"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        raise ToolError(f"I couldn't find a place called '{location}'.")
    hint = hint.strip().lower()
    if hint:
        for r in results:
            where = " ".join(str(r.get(k, "")) for k in ("country", "country_code", "admin1")).lower()
            if hint in where:
                return r
    return results[0]


@tool(
    "get_weather",
    "Current weather and a 3-day forecast for a place. If the user doesn't say "
    "where, use their home city.",
    {
        "location": {"type": "string", "description": "City, optionally with country: 'Paris, France'."},
        "units": {"type": "string", "enum": ["celsius", "fahrenheit"]},
    },
)
def get_weather(ctx: Context, args: dict) -> str:
    location = (args.get("location") or ctx.settings.home_city).strip()
    if not location:
        raise ToolError("No location given and no HOME_CITY is configured; ask the user where.")
    units = args.get("units") or "celsius"
    place = geocode(location)
    resp = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": units,
            "timezone": "auto",
            "forecast_days": 3,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    unit = "°F" if units == "fahrenheit" else "°C"
    cur = data["current"]
    name = ", ".join(p for p in (place.get("name"), place.get("admin1"), place.get("country")) if p)
    lines = [
        f"Weather in {name}:",
        f"Now: {cur['temperature_2m']}{unit} (feels like {cur['apparent_temperature']}{unit}), "
        f"{WEATHER_CODES.get(cur['weather_code'], 'unknown')}, humidity {cur['relative_humidity_2m']}%, "
        f"wind {cur['wind_speed_10m']} km/h.",
    ]
    daily = data["daily"]
    for i, day in enumerate(daily["time"]):
        lines.append(
            f"{day}: {WEATHER_CODES.get(daily['weather_code'][i], 'unknown')}, "
            f"{daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}{unit}, "
            f"{daily['precipitation_probability_max'][i]}% chance of rain."
        )
    return "\n".join(lines)
