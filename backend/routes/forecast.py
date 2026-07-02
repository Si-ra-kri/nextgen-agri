"""
routes/forecast.py
GET /api/forecast          — real 7-day weather forecast (Open-Meteo, no API key)
GET /api/geocode           — text → lat/lon (Open-Meteo geocoding, no key)
GET /api/reverse-geocode   — lat/lon → place name (Nominatim OSM, no key)

All three external services are free and require no API key.
"""

import httpx
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL  = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_URL  = "https://nominatim.openstreetmap.org/reverse"

# WMO weather interpretation codes → (emoji, description)
WMO_MAP = {
    0:  ("☀️",  "Clear sky"),
    1:  ("🌤️", "Mainly clear"),
    2:  ("⛅",  "Partly cloudy"),
    3:  ("☁️",  "Overcast"),
    45: ("🌫️", "Foggy"),
    48: ("🌫️", "Freezing fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Drizzle"),
    55: ("🌧️", "Heavy drizzle"),
    61: ("🌧️", "Light rain"),
    63: ("🌧️", "Moderate rain"),
    65: ("🌧️", "Heavy rain"),
    71: ("🌨️", "Light snow"),
    73: ("🌨️", "Moderate snow"),
    75: ("❄️",  "Heavy snow"),
    80: ("🌦️", "Rain showers"),
    81: ("🌧️", "Moderate showers"),
    82: ("⛈️",  "Violent showers"),
    95: ("⛈️",  "Thunderstorm"),
    96: ("⛈️",  "Thunderstorm + hail"),
    99: ("⛈️",  "Thunderstorm + heavy hail"),
}

def _wmo(code: int):
    return WMO_MAP.get(code, ("🌤️", "Partly cloudy"))


@router.get("/forecast")
async def get_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """
    Real 7-day daily forecast from Open-Meteo (globally available, no API key).
    Returns rain, temperature, evapotranspiration, and an irrigate/skip decision
    for each day based on expected rainfall.
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "daily": [
            "weathercode",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "et0_fao_evapotranspiration",
        ],
        "timezone":     "auto",
        "forecast_days": 7,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Open-Meteo unavailable: {e}")

    daily   = raw.get("daily", {})
    dates   = daily.get("time", [])
    codes   = daily.get("weathercode", [])
    t_max   = daily.get("temperature_2m_max", [])
    t_min   = daily.get("temperature_2m_min", [])
    precip  = daily.get("precipitation_sum", [])
    et0     = daily.get("et0_fao_evapotranspiration", [])

    days = []
    for i in range(len(dates)):
        rain     = float(precip[i]) if i < len(precip) else 0.0
        code     = int(codes[i])    if i < len(codes)  else 0
        icon, desc = _wmo(code)
        # Irrigate if < 4 mm rain expected that day
        irrigate = rain < 4.0
        days.append({
            "date":         dates[i],
            "day_label":    ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i % 7],
            "weather_code": code,
            "weather_icon": icon,
            "weather_desc": desc,
            "rain_mm":      round(rain, 1),
            "temp_max_c":   round(float(t_max[i]), 1)  if i < len(t_max)  else None,
            "temp_min_c":   round(float(t_min[i]), 1)  if i < len(t_min)  else None,
            "et0_mm":       round(float(et0[i]),   1)  if i < len(et0)    else None,
            "irrigate":     irrigate,
            "action":       "Irrigate" if irrigate else f"Skip — {rain} mm rain expected",
        })

    return {
        "latitude":  lat,
        "longitude": lon,
        "timezone":  raw.get("timezone", ""),
        "days":      days,
        "source":    "Open-Meteo (open-meteo.com)",
    }


@router.get("/geocode")
async def geocode(
    q: str = Query(..., description="Location name to geocode"),
):
    """
    Text → lat/lon using Open-Meteo Geocoding API (no API key, global).
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                GEOCODING_URL,
                params={"name": q, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding error: {e}")

    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=404, detail=f"Location '{q}' not found. Try a more specific name.")

    r = results[0]
    return {
        "name":         r.get("name", ""),
        "country":      r.get("country", ""),
        "admin1":       r.get("admin1", ""),
        "latitude":     r["latitude"],
        "longitude":    r["longitude"],
        "display_name": f"{r.get('name','')}, {r.get('admin1','')}, {r.get('country','')}",
    }


@router.get("/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(...),
    lon: float = Query(...),
):
    """
    lat/lon → human-readable place name using Nominatim (OpenStreetMap).
    No API key required.
    """
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"User-Agent": "NextGenAgri/3.0 (hackathon@nextgenagri.ai)"},
        ) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"format": "json", "lat": lat, "lon": lon, "zoom": 10},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Reverse geocode error: {e}")

    addr    = data.get("address", {})
    city    = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county", "")
    state   = addr.get("state", "")
    country = addr.get("country", "")
    display = ", ".join(filter(None, [city, state, country]))

    return {
        "display_name": display or data.get("display_name", f"{lat:.4f}, {lon:.4f}"),
        "city":    city,
        "state":   state,
        "country": country,
    }
