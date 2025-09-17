#!/usr/bin/env python3
"""
Simple weather module for Europa startup display.
Provides current weather based on IP geolocation.
"""

from typing import Optional

import requests


def get_location() -> Optional[dict]:
    """Get user location from IP with multiple fallbacks."""
    apis = ["https://ipinfo.io/json", "https://ipapi.co/json", "https://httpbin.org/ip"]

    for api in apis:
        try:
            response = requests.get(api, timeout=2)
            data = response.json()

            if "city" in data:
                return {
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", data.get("country_name", "XX")),
                    "loc": data.get("loc", "51.5074,-0.1278"),
                }
        except Exception:
            continue

    return {"city": "London", "country": "GB", "loc": "51.5074,-0.1278"}


def get_weather_data(lat: str, lon: str) -> Optional[dict]:
    """Get weather data from wttr.in API."""
    try:
        response = requests.get(f"https://wttr.in/{lat},{lon}?format=j1", timeout=3)
        return response.json()
    except Exception:
        return None


def get_weather_emoji(condition: str) -> str:
    """Get emoji for weather condition."""
    condition_lower = condition.lower()

    emoji_map = {
        "clear": "☀️",
        "sunny": "☀️",
        "partly cloudy": "⛅",
        "partly_cloudy": "⛅",
        "cloudy": "☁️",
        "overcast": "☁️",
        "mist": "🌫️",
        "fog": "🌫️",
        "light rain": "🌦️",
        "rain": "🌧️",
        "heavy rain": "🌧️",
        "drizzle": "🌦️",
        "shower": "🌦️",
        "thunderstorm": "⛈️",
        "thunder": "⛈️",
        "snow": "❄️",
        "light snow": "🌨️",
        "heavy snow": "❄️",
        "sleet": "🌨️",
        "hail": "🌨️",
        "windy": "💨",
        "breezy": "🍃",
    }

    for key, emoji in emoji_map.items():
        if key in condition_lower:
            return emoji

    return "🌤️"


def format_weather_info(location: dict, weather_data: dict) -> str:
    """Format weather information for display."""
    try:
        current = weather_data["current_condition"][0]
        temp = current["temp_C"]
        condition = current["weatherDesc"][0]["value"]
        emoji = get_weather_emoji(condition)

        return f"{location['city']}, {location['country']} {temp}°C {emoji}  {condition}"
    except Exception:
        return f"{location['city']}, {location['country']} Weather unavailable"


def get_simple_weather() -> str:
    """Get simple weather info for startup display."""
    try:
        location = get_location()
        if not location:
            return "Weather unavailable"

        lat, lon = location["loc"].split(",")

        weather_data = get_weather_data(lat.strip(), lon.strip())
        if not weather_data:
            return f"{location['city']}, {location['country']} Weather unavailable"

        return format_weather_info(location, weather_data)

    except Exception:
        return "Weather unavailable"


if __name__ == "__main__":
    print(get_simple_weather())
