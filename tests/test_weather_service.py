"""Mocked weather-service checks; no external network or Pi hardware needed."""
import unittest

from weather_service import fetch_weather, parse_weather


def modern_payload(temperature=0):
    return {
        "current": {
            "temperature_2m": temperature,
            "relative_humidity_2m": 82,
            "weather_code": 3,
        },
        "daily": {
            "time": ["2026-11-10", "2026-11-11"],
            "weather_code": [3, 61],
            "temperature_2m_max": [12.6, 10.4],
            "temperature_2m_min": [4.2, 2.8],
        },
    }


class WeatherParserTests(unittest.TestCase):
    def test_modern_response_accepts_zero_degrees(self):
        result = parse_weather(modern_payload())
        self.assertEqual(result["temperature"], 0)
        self.assertEqual(result["humidity"], 82)
        self.assertEqual(result["weather_code"], 3)
        self.assertEqual(len(result["forecast"]), 2)
        self.assertEqual(result["forecast"][0]["high"], 13)

    def test_legacy_response_still_supported(self):
        result = parse_weather({
            "current_weather": {"temperature": 8.2, "weathercode": 2},
            "daily": {},
        })
        self.assertEqual(result["temperature"], 8)
        self.assertIsNone(result["humidity"])
        self.assertEqual(result["weather_code"], 2)

    def test_bad_response_raises_instead_of_using_fake_temperature(self):
        for data in ({}, {"error": True, "reason": "bad location"},
                     {"current": {"temperature_2m": None, "weather_code": 0}}):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    parse_weather(data)

    def test_fetch_surfaces_http_errors(self):
        class FakeResponse:
            def raise_for_status(self):
                raise RuntimeError("HTTP 503")
        def fake_get(url, timeout):
            self.assertEqual(timeout, (4, 10))
            raise_if_not_https(url)
            return FakeResponse()
        with self.assertRaisesRegex(RuntimeError, "503"):
            fetch_weather("https://api.open-meteo.com/v1/forecast", get=fake_get)

    def test_fetch_valid_data(self):
        class FakeResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return modern_payload(6.5)
        result = fetch_weather("https://api.open-meteo.com", get=lambda url, timeout: FakeResponse())
        self.assertEqual(result["temperature"], 6)

    def test_invalid_daily_entries_do_not_crash_live_weather(self):
        payload = modern_payload(9)
        payload["daily"]["temperature_2m_max"][0] = None
        result = parse_weather(payload)
        self.assertEqual(len(result["forecast"]), 1)
        self.assertEqual(result["temperature"], 9)


def raise_if_not_https(url):
    if not url.startswith("https://"):
        raise AssertionError("Only HTTPS weather endpoints should be used")


if __name__ == "__main__":
    unittest.main()
