import math
from typing import Any

import httpx
from flask import Flask, jsonify, render_template, request


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 8.0

app = Flask(__name__)


class CityNotFound(Exception):
    pass


class WeatherProviderError(Exception):
    pass


class WeatherProviderTimeout(Exception):
    pass


WEATHER_CODES = {
    0: ("Clear sky", "clear"),
    1: ("Mainly clear", "clear"),
    2: ("Partly cloudy", "partly-cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Moderate drizzle", "drizzle"),
    55: ("Dense drizzle", "drizzle"),
    56: ("Light freezing drizzle", "drizzle"),
    57: ("Dense freezing drizzle", "drizzle"),
    61: ("Slight rain", "rain"),
    63: ("Moderate rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Light freezing rain", "rain"),
    67: ("Heavy freezing rain", "rain"),
    71: ("Slight snowfall", "snow"),
    73: ("Moderate snowfall", "snow"),
    75: ("Heavy snowfall", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Slight rain showers", "showers"),
    81: ("Moderate rain showers", "showers"),
    82: ("Heavy rain showers", "showers"),
    85: ("Slight snow showers", "snow-showers"),
    86: ("Heavy snow showers", "snow-showers"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm with light hail", "thunderstorm"),
    99: ("Thunderstorm with heavy hail", "thunderstorm"),
}


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as error:
        raise WeatherProviderTimeout from error
    except (httpx.HTTPError, ValueError) as error:
        raise WeatherProviderError from error


def _icon_key(icon_family: str, is_day: bool) -> str:
    if icon_family in {"clear", "partly-cloudy"}:
        time_of_day = "day" if is_day else "night"
        return f"{icon_family}-{time_of_day}"
    return icon_family


def get_current_weather(city: str, unit: str) -> dict[str, Any]:
    location_data = _get_json(
        GEOCODING_URL,
        {"name": city, "count": 1, "language": "en", "format": "json"},
    )
    locations = location_data.get("results", [])
    if not locations:
        raise CityNotFound

    location = locations[0]
    temperature_unit = "celsius" if unit == "celsius" else "fahrenheit"
    wind_speed_unit = "kmh" if unit == "celsius" else "mph"
    weather_data = _get_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "is_day,weather_code,wind_speed_10m"
            ),
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "timezone": "auto",
        },
    )

    try:
        current = weather_data["current"]
        weather_code = int(current["weather_code"])
        is_day = int(current["is_day"]) == 1
        condition, icon_family = WEATHER_CODES.get(
            weather_code, ("Conditions unavailable", "cloudy")
        )
        temperature = float(current["temperature_2m"])
        feels_like = float(current["apparent_temperature"])
        humidity = int(current["relative_humidity_2m"])
        wind_speed = float(current["wind_speed_10m"])
        if not all(math.isfinite(value) for value in (temperature, feels_like, wind_speed)):
            raise ValueError("Weather response contains a non-finite value.")

        return {
            "city": location["name"],
            "region": location.get("admin1", ""),
            "country": location.get("country", ""),
            "temperature": temperature,
            "feels_like": feels_like,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "temperature_unit": "°C" if unit == "celsius" else "°F",
            "wind_unit": "km/h" if unit == "celsius" else "mph",
            "condition": condition,
            "weather_code": weather_code,
            "is_day": is_day,
            "icon_key": _icon_key(icon_family, is_day),
            "timezone": weather_data["timezone"],
            "observed_at": current["time"],
        }
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise WeatherProviderError from error


@app.get("/")
def home() -> str:
    return render_template("weather.html")


@app.post("/api/weather")
def weather() -> tuple[Any, int] | Any:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a city and temperature unit."}), 400

    city = payload.get("city")
    if not isinstance(city, str) or not city.strip():
        return jsonify({"error": "Enter a city name."}), 400
    city = city.strip()
    if len(city) > 100:
        return jsonify({"error": "City names must be 100 characters or fewer."}), 400

    unit = payload.get("unit", "celsius")
    if not isinstance(unit, str) or unit not in {"celsius", "fahrenheit"}:
        return jsonify({"error": "Choose Celsius or Fahrenheit."}), 400

    try:
        return jsonify(get_current_weather(city, unit))
    except CityNotFound:
        return jsonify({"error": f"No weather location found for {city}."}), 404
    except WeatherProviderTimeout:
        return jsonify({"error": "The weather service took too long to respond. Try again."}), 504
    except WeatherProviderError:
        app.logger.exception("Weather provider request failed")
        return jsonify({"error": "Weather data is temporarily unavailable. Try again."}), 502


if __name__ == "__main__":
    app.run(debug=True)