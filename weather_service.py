"""Open-Meteo weather parsing and resilient retrieval for PiRadio.

No GUI code or side effects at import. The Pi's UI thread can fetch via a
background worker and consume the normalized result when it is ready.
"""
from datetime import datetime
import math
import requests


def _number(value, label):
    if value is None:
        raise ValueError(f"Weather API missing {label}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Weather API returned invalid {label}")
    return number


def parse_weather(payload):
    """Accept the current Open-Meteo format, with a legacy current_weather fallback."""
    if not isinstance(payload, dict):
        raise ValueError("Weather API returned an invalid response")
    if payload.get("error"):
        raise ValueError(str(payload.get("reason") or "Weather API error"))

    current = payload.get("current") or {}
    legacy = payload.get("current_weather") or {}
    temperature = _number(
        current.get("temperature_2m", legacy.get("temperature")), "temperature"
    )
    code = int(_number(
        current.get("weather_code", legacy.get("weathercode")), "weather code"
    ))
    raw_humidity = current.get("relative_humidity_2m")
    humidity = None
    if raw_humidity is not None:
        try:
            humidity_value = _number(raw_humidity, "humidity")
            if 0 <= humidity_value <= 100:
                humidity = int(round(humidity_value))
        except (TypeError, ValueError):
            pass

    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    forecast = []
    for date, daily_code, high, low in zip(dates, codes, highs, lows):
        if daily_code is None or high is None or low is None:
            continue
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            forecast.append({
                "day": dt.strftime("%a"),
                "weather_code": int(_number(daily_code, "daily weather code")),
                "high": int(round(_number(high, "high temperature"))),
                "low": int(round(_number(low, "low temperature"))),
            })
        except (TypeError, ValueError):
            continue

    return {
        "temperature": int(round(temperature)),
        "humidity": humidity,
        "weather_code": code,
        "forecast": forecast,
    }


def fetch_weather(url, timeout=(4, 10), get=None):
    """Raise a descriptive exception on HTTP, transport, or schema failures."""
    client_get = get or requests.get
    response = client_get(url, timeout=timeout)
    response.raise_for_status()
    return parse_weather(response.json())
