import unittest
from unittest.mock import Mock, patch

import httpx

from weather_app import FORECAST_URL, GEOCODING_URL, app


def provider_response(data: dict) -> Mock:
    response = Mock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


class WeatherAppTests(unittest.TestCase):
    def setUp(self) -> None:
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_home_serves_weather_page_and_assets(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Weather,", page.data)
        with self.client.get("/static/weather.css") as css_response:
            self.assertEqual(css_response.status_code, 200)
        with self.client.get("/static/weather.js") as js_response:
            self.assertEqual(js_response.status_code, 200)

    @patch("weather_app.httpx.get")
    def test_successful_lookup_normalizes_current_conditions(self, get: Mock) -> None:
        get.side_effect = [
            provider_response(
                {
                    "results": [
                        {
                            "name": "Reykjavik",
                            "admin1": "Capital Region",
                            "country": "Iceland",
                            "latitude": 64.14,
                            "longitude": -21.94,
                        }
                    ]
                }
            ),
            provider_response(
                {
                    "timezone": "Atlantic/Reykjavik",
                    "current": {
                        "time": "2026-09-29T14:00",
                        "temperature_2m": 11.4,
                        "relative_humidity_2m": 72,
                        "apparent_temperature": 9.8,
                        "is_day": 1,
                        "weather_code": 61,
                        "wind_speed_10m": 18.2,
                    },
                }
            ),
        ]

        response = self.client.post(
            "/api/weather", json={"city": "  Reykjavik ", "unit": "celsius"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "city": "Reykjavik",
                "region": "Capital Region",
                "country": "Iceland",
                "temperature": 11.4,
                "feels_like": 9.8,
                "humidity": 72,
                "wind_speed": 18.2,
                "temperature_unit": "°C",
                "wind_unit": "km/h",
                "condition": "Slight rain",
                "weather_code": 61,
                "is_day": True,
                "icon_key": "rain",
                "timezone": "Atlantic/Reykjavik",
                "observed_at": "2026-09-29T14:00",
            },
        )
        self.assertEqual(get.call_args_list[0].args[0], GEOCODING_URL)
        self.assertEqual(get.call_args_list[1].args[0], FORECAST_URL)

    @patch("weather_app.httpx.get")
    def test_fahrenheit_uses_matching_provider_units(self, get: Mock) -> None:
        get.side_effect = [
            provider_response(
                {"results": [{"name": "Boston", "latitude": 42.36, "longitude": -71.06}]}
            ),
            provider_response(
                {
                    "timezone": "America/New_York",
                    "current": {
                        "time": "2026-09-29T10:00",
                        "temperature_2m": 68,
                        "relative_humidity_2m": 50,
                        "apparent_temperature": 68,
                        "is_day": 1,
                        "weather_code": 0,
                        "wind_speed_10m": 4,
                    },
                }
            ),
        ]

        response = self.client.post(
            "/api/weather", json={"city": "Boston", "unit": "fahrenheit"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["temperature_unit"], "°F")
        self.assertEqual(response.json["wind_unit"], "mph")
        self.assertEqual(response.json["icon_key"], "clear-day")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["temperature_unit"], "fahrenheit")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["wind_speed_unit"], "mph")

    @patch("weather_app.httpx.get")
    def test_unknown_city_returns_not_found(self, get: Mock) -> None:
        get.return_value = provider_response({"results": []})

        response = self.client.post("/api/weather", json={"city": "Nowhere"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("No weather location found", response.json["error"])
        get.assert_called_once()

    @patch("weather_app.httpx.get")
    def test_invalid_input_does_not_call_provider(self, get: Mock) -> None:
        empty_city = self.client.post("/api/weather", json={"city": " "})
        bad_unit = self.client.post(
            "/api/weather", json={"city": "Boston", "unit": "kelvin"}
        )
        invalid_unit_type = self.client.post(
            "/api/weather", json={"city": "Boston", "unit": ["celsius"]}
        )
        long_city = self.client.post("/api/weather", json={"city": "x" * 101})

        self.assertEqual(empty_city.status_code, 400)
        self.assertEqual(bad_unit.status_code, 400)
        self.assertEqual(invalid_unit_type.status_code, 400)
        self.assertEqual(long_city.status_code, 400)
        get.assert_not_called()

    @patch("weather_app.httpx.get", side_effect=httpx.TimeoutException("timed out"))
    def test_provider_timeout_returns_gateway_timeout(self, get: Mock) -> None:
        response = self.client.post("/api/weather", json={"city": "Boston"})

        self.assertEqual(response.status_code, 504)
        self.assertIn("took too long", response.json["error"])

    @patch("weather_app.httpx.get", side_effect=httpx.HTTPError("provider unavailable"))
    def test_provider_error_returns_bad_gateway(self, get: Mock) -> None:
        response = self.client.post("/api/weather", json={"city": "Boston"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("temporarily unavailable", response.json["error"])


if __name__ == "__main__":
    unittest.main()