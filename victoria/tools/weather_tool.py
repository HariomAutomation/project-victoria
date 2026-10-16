"""
Victoria - Weather Tool
Fetch real-time weather information for any city/location quickly.
"""

import urllib.request
import json
import urllib.parse


def get_weather(city: str = "Varanasi") -> str:
    """
    Get live weather forecast and conditions for a given city.
    """
    cleaned_city = city.strip() or "Varanasi"
    encoded_city = urllib.parse.quote(cleaned_city)
    
    # Try wttr.in JSON API first
    try:
        url = f"https://wttr.in/{encoded_city}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            current = data.get("current_condition", [{}])[0]
            temp_c = current.get("temp_C", "")
            desc = current.get("weatherDesc", [{}])[0].get("value", "")
            humidity = current.get("humidity", "")
            wind_kmph = current.get("windspeedKmph", "")
            return f"हरिओम जी, {cleaned_city} का तापमान {temp_c}°C है, मौसम '{desc}' है, नमी {humidity}% और हवा {wind_kmph} km/h है।"
    except Exception:
        pass

    # Fallback to Open-Meteo Geocoding + Weather API
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1"
        with urllib.request.urlopen(geo_url, timeout=4) as g_resp:
            g_data = json.loads(g_resp.read().decode("utf-8"))
            results = g_data.get("results", [])
            if results:
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]
                name = results[0]["name"]
                w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto"
                with urllib.request.urlopen(w_url, timeout=4) as w_resp:
                    w_data = json.loads(w_resp.read().decode("utf-8"))
                    cur = w_data.get("current", {})
                    temp = cur.get("temperature_2m")
                    hum = cur.get("relative_humidity_2m")
                    wind = cur.get("wind_speed_10m")
                    return f"हरिओम जी, {name} का तापमान {temp}°C है, नमी {hum}% और हवा {wind} km/h है।"
    except Exception as e:
        return f"{cleaned_city} का मौसम लोड नहीं हो सका: {e}"

    return f"हरिओम जी, {cleaned_city} का मौसम डेटा अभी उपलब्ध नहीं हो सका।"
