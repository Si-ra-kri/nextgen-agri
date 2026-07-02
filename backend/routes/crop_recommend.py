"""
routes/crop_recommend.py
POST /api/recommend/crop

User supplies only a free-text location ("Thanjavur, Tamil Nadu").
The backend automatically:
- Geocodes and fetches current weather from OpenWeatherMap
- Infers current season from month
- Scans recent calamity news via NewsAPI
- Looks up soil profile by Indian state
Then runs the crop recommendation model (or a rule-based fallback).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Request

from schemas.crop_recommend import (
    AutoDetectedInfo,
    CropRank,
    CropRecommendRequest,
    CropRecommendResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Soil profiles by Indian state ─────────────────────────────────────────────
SOIL_PROFILES: Dict[str, Dict[str, float]] = {
    "Tamil Nadu": {"N": 80, "P": 40, "K": 45, "ph": 6.5},
    "Maharashtra": {"N": 70, "P": 35, "K": 40, "ph": 6.8},
    "Punjab": {"N": 90, "P": 50, "K": 55, "ph": 7.2},
    "Karnataka": {"N": 75, "P": 38, "K": 42, "ph": 6.6},
    "Andhra Pradesh": {"N": 78, "P": 42, "K": 44, "ph": 6.7},
    "Uttar Pradesh": {"N": 85, "P": 48, "K": 50, "ph": 7.0},
    "West Bengal": {"N": 82, "P": 44, "K": 46, "ph": 6.4},
    "Gujarat": {"N": 72, "P": 36, "K": 41, "ph": 7.1},
    "Rajasthan": {"N": 65, "P": 32, "K": 38, "ph": 7.6},
    "Bihar": {"N": 80, "P": 40, "K": 45, "ph": 6.9},
    "Odisha": {"N": 78, "P": 39, "K": 43, "ph": 6.6},
    "Telangana": {"N": 76, "P": 37, "K": 42, "ph": 6.7},
    "Kerala": {"N": 88, "P": 45, "K": 50, "ph": 5.8},
    "Madhya Pradesh": {"N": 83, "P": 41, "K": 47, "ph": 6.9},
    "Haryana": {"N": 87, "P": 43, "K": 48, "ph": 7.3},
    "Jharkhand": {"N": 79, "P": 38, "K": 44, "ph": 6.5},
    "Assam": {"N": 81, "P": 40, "K": 46, "ph": 6.2},
    "Chhattisgarh": {"N": 77, "P": 37, "K": 43, "ph": 6.6},
    "default": {"N": 75, "P": 40, "K": 43, "ph": 6.8},
}

# ── Class labels (must match training/train_recommend.py) ─────────────────────
CROP_LABELS = [
    "Rice",
    "Maize",
    "Chickpea",
    "Kidney Beans",
    "Pigeon Peas",
    "Moth Beans",
    "Mung Bean",
    "Black-eyed Peas",
    "Lentil",
    "Pomegranate",
    "Banana",
    "Mango",
    "Grapes",
    "Watermelon",
    "Muskmelon",
    "Apple",
    "Orange",
    "Papaya",
    "Coconut",
    "Cotton",
    "Jute",
    "Coffee",
]

# ── Calamity penalisation: down-rank unsuitable crops ────────────────────────
CALAMITY_PENALTY = {
    "Flood": {"Cotton", "Groundnut", "Maize"},
    "Drought": {"Rice", "Sugarcane", "Jute"},
    "Cyclone": {"Banana", "Papaya", "Coffee"},
    "Hailstorm": {"Grapes", "Apple", "Mango", "Watermelon"},
    "None": set(),
}

# Calamity advisories
CALAMITY_ADVISORIES = {
    "None": "Conditions look normal. You can proceed with standard crop planning.",
    "Flood": "Post-flood: avoid deep-root crops for 3 weeks. Prefer short-duration, flood-tolerant varieties.",
    "Drought": "Drought conditions: prioritise drought-resistant crops with low water requirement.",
    "Cyclone": "Post-cyclone: avoid tall or large-canopy crops. Prefer resilient short-stature varieties.",
    "Hailstorm": "Hailstorm damage: avoid fragile fruit crops. Choose hardy grains or legumes.",
}

# Human-readable reason per crop (simplified)
CROP_REASONS = {
    "Rice": "High-yield staple, suitable for wet soils",
    "Maize": "Versatile, grows well in loamy soil",
    "Chickpea": "Drought-tolerant, nitrogen-fixing legume",
    "Kidney Beans": "Protein-rich, moderate water requirement",
    "Pigeon Peas": "Drought-resistant, popular in dry Kharif",
    "Moth Beans": "Arid-region specialist, very low water need",
    "Mung Bean": "Fast-maturing, suits post-flood recovery",
    "Black-eyed Peas": "Flood-resistant, fast maturing, high demand",
    "Lentil": "Cool season crop, ideal for Rabi",
    "Pomegranate": "High market value, low water requirement",
    "Banana": "High-yield, needs well-drained soil",
    "Mango": "Long-term investment, high export value",
    "Grapes": "Premium fruit, well-suited to dry climate",
    "Watermelon": "High water content required but fast yield",
    "Muskmelon": "Short season crop, good market demand",
    "Apple": "Cool climate crop, premium pricing",
    "Orange": "Evergreen, steady demand",
    "Papaya": "Fast-growing, high nutrition value",
    "Coconut": "Perennial, suited to coastal regions",
    "Cotton": "Cash crop, requires dry post-kharif weather",
    "Jute": "Suited to humid, waterlogged conditions",
    "Coffee": "High-value export crop, needs shade",
    "Sorghum": "Tolerates waterlogged soil, drought-resistant",
    "Pearl Millet": "High demand, drought-tolerant post-flood",
}


def _infer_season_from_month(month: int) -> str:
    if 6 <= month <= 10:
        return "Kharif"
    if 11 <= month or month == 1 or month == 2 or month == 3:
        return "Rabi"
    return "Zaid"


def _extract_state(location: str) -> str:
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return parts[0] if parts else ""


def _soil_profile_for_location(location: str) -> Dict[str, float]:
    state = _extract_state(location)
    for key, vals in SOIL_PROFILES.items():
        if key.lower() == state.lower():
            return vals
    return SOIL_PROFILES["default"]


async def _fetch_weather(location: str) -> Dict[str, Any]:
    """
    Fetch current weather for a location.
    Primary:  Open-Meteo geocoding + current conditions (no API key needed).
    Fallback: OpenWeatherMap if OPENWEATHER_API_KEY is set and Open-Meteo fails.
    Last resort: sensible regional defaults so the endpoint never errors.
    """
    # ── Try Open-Meteo (always available, no key) ──────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: geocode via Open-Meteo
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            geo_resp.raise_for_status()
            results = geo_resp.json().get("results", [])
            if not results:
                raise ValueError(f"Location '{location}' not found via Open-Meteo geocoding")

            lat = results[0]["latitude"]
            lon = results[0]["longitude"]

            # Step 2: current conditions (hourly, first value = now)
            wx_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation"],
                    "forecast_days": 1, "timezone": "auto",
                },
            )
            wx_resp.raise_for_status()
            hourly = wx_resp.json().get("hourly", {})

            temp     = float(hourly.get("temperature_2m",       [25.0])[0] or 25.0)
            humidity = float(hourly.get("relative_humidity_2m", [60.0])[0] or 60.0)
            rainfall = float(hourly.get("precipitation",        [0.0])[0]  or 0.0)

            # Describe condition from rain
            if rainfall > 5:
                condition = "Heavy rain"
            elif rainfall > 0.5:
                condition = "Light rain"
            elif humidity > 80:
                condition = "Cloudy"
            else:
                condition = "Clear sky"

        return {"temperature": temp, "humidity": humidity,
                "rainfall": rainfall, "condition": condition}

    except Exception as open_meteo_err:
        logger.warning("Open-Meteo weather fetch failed: %s", open_meteo_err)

    # ── Try OpenWeatherMap if key is available ─────────────────────────────────
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                geo_resp = await client.get(
                    "http://api.openweathermap.org/geo/1.0/direct",
                    params={"q": location, "limit": 1, "appid": api_key},
                )
                geo_resp.raise_for_status()
                geo_data = geo_resp.json()
                if geo_data:
                    lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]
                    w = (await client.get(
                        "https://api.openweathermap.org/data/2.5/weather",
                        params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                    )).json()
                    return {
                        "temperature":      float(w["main"]["temp"]),
                        "humidity":         float(w["main"]["humidity"]),
                        "rainfall":         float(w.get("rain",{}).get("1h", 0) or 0),
                        "condition":        w.get("weather",[{}])[0].get("description","").title(),
                    }
        except Exception as owm_err:
            logger.warning("OpenWeatherMap fallback also failed: %s", owm_err)

    # ── Last-resort regional defaults — never return a 500 ────────────────────
    logger.warning("All weather sources failed for '%s' — using regional defaults", location)
    return {"temperature": 28.0, "humidity": 65.0, "rainfall": 0.0, "condition": "Partly cloudy"}

    async with httpx.AsyncClient(timeout=10) as client:
        geo_resp = await client.get(
            "http://api.openweathermap.org/geo/1.0/direct",
            params={"q": location, "limit": 1, "appid": api_key},
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise HTTPException(
                status_code=404,
                detail=f"Could not geocode location '{location}'. Please check the name and try again.",
            )

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        weather_resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        )
        weather_resp.raise_for_status()
        w = weather_resp.json()

    temp = float(w["main"]["temp"])
    humidity = float(w["main"]["humidity"])
    rainfall = float(w.get("rain", {}).get("1h", 0.0) or w.get("rain", {}).get("3h", 0.0) or 0.0)
    condition = w.get("weather", [{}])[0].get("description", "Unknown").title()

    return {
        "temperature": temp,
        "humidity": humidity,
        "rainfall": rainfall,
        "condition": condition,
    }


def _parse_calamity_from_articles(articles: list[Dict[str, Any]]) -> Tuple[str, str | None]:
    keywords = {
        "flood": "Flood",
        "drought": "Drought",
        "cyclone": "Cyclone",
        "hailstorm": "Hailstorm",
        "earthquake": "Earthquake",
        "landslide": "Landslide",
    }

    now = datetime.now(timezone.utc)
    best_type = "None"
    best_source = None
    best_time = None

    for art in articles:
        text = f"{art.get('title', '')} {art.get('description', '')}".lower()
        found_type = None
        for kw, label in keywords.items():
            if kw in text:
                found_type = label
                break
        if not found_type:
            continue

        published_str = art.get("publishedAt")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except Exception:
            published = now

        if (now - published).days > 30:
            continue

        if best_time is None or published > best_time:
            best_time = published
            best_type = found_type
            source_name = art.get("source", {}).get("name") or "News source"
            days_ago = max((now - published).days, 0)
            if days_ago == 0:
                rel = "today"
            elif days_ago == 1:
                rel = "1 day ago"
            else:
                rel = f"{days_ago} days ago"
            best_source = f"{source_name} - {rel}"

    return best_type, best_source


async def _fetch_recent_calamity(location: str) -> Tuple[str, str | None]:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        # Graceful fallback if NewsAPI not configured
        return "None", None

    district = location.split(",")[0].strip()
    query = f"{district} flood OR drought OR cyclone OR calamity OR hailstorm OR landslide OR earthquake"
    from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": api_key,
                "from": from_date,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    articles = data.get("articles", [])
    cal_type, source = _parse_calamity_from_articles(articles)
    return cal_type, source


def _rule_based_recommend(season: str, calamity: str) -> list[Dict[str, Any]]:
    penalised = CALAMITY_PENALTY.get(calamity, set())
    # Simple season-based defaults
    season_defaults = {
        "Kharif": ["Rice", "Mung Bean", "Pigeon Peas", "Sorghum", "Pearl Millet"],
        "Rabi": ["Chickpea", "Lentil", "Kidney Beans"],
        "Zaid": ["Watermelon", "Muskmelon", "Maize"],
    }
    crops = [c for c in (season_defaults.get(season) or ["Rice", "Mung Bean", "Chickpea"]) if c not in penalised]

    # Pad if needed
    all_options = [c for c in CROP_LABELS if c not in penalised]
    while len(crops) < 3 and all_options:
        c = all_options.pop(0)
        if c not in crops:
            crops.append(c)

    return [
        {"crop": crops[i], "confidence": round(0.91 - i * 0.07, 2)}
        for i in range(min(3, len(crops)))
    ]


@router.post("/crop", response_model=CropRecommendResponse)
async def recommend_crop(req: CropRecommendRequest, request: Request):
    """Fully automatic crop recommendation based only on free-text location."""

    location = req.location.strip()
    if not location:
        raise HTTPException(status_code=400, detail="Location is required")

    try:
        weather = await _fetch_weather(location)
    except httpx.HTTPError as e:
        logger.error("Weather fetch failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Could not fetch weather data for this location. Please check the name and try again.",
        )

    try:
        calamity_type, calamity_source = await _fetch_recent_calamity(location)
    except httpx.HTTPError as e:
        logger.error("News API fetch failed: %s", e)
        calamity_type, calamity_source = "None", None

    soil = _soil_profile_for_location(location)
    season = _infer_season_from_month(datetime.utcnow().month)

    season_enc = {"Kharif": 0, "Rabi": 1, "Zaid": 2}
    calamity_enc = {"None": 0, "Flood": 1, "Drought": 2, "Cyclone": 3, "Hailstorm": 4}

    model = getattr(request.app.state, "recommend_model", None)
    model_classes = getattr(request.app.state, "recommend_classes", None) or CROP_LABELS
    penalised = CALAMITY_PENALTY.get(calamity_type, set())

    ranked: list[CropRank]

    if model is not None:
        features = np.array(
            [
                [
                    soil["N"],
                    soil["P"],
                    soil["K"],
                    weather["temperature"],
                    weather["humidity"],
                    soil["ph"],
                    weather.get("rainfall", 0.0),
                    calamity_enc.get(calamity_type, 0),
                    season_enc.get(season, 0),
                ]
            ]
        )

        try:
            proba = model.predict_proba(features)[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Model inference failed: {str(e)}")

        for i, label in enumerate(model_classes):
            if i < len(proba) and label in penalised:
                proba[i] = 0.0

        top_indices = sorted(range(len(proba)), key=lambda i: proba[i], reverse=True)[:3]
        ranked = []
        for rank, idx in enumerate(top_indices, start=1):
            label = model_classes[idx] if idx < len(model_classes) else "Rice"
            ranked.append(
                CropRank(
                    rank=rank,
                    crop=label,
                    confidence=round(float(proba[idx]), 2),
                    reason=CROP_REASONS.get(label, "Well-suited to local conditions"),
                )
            )
    else:
        raw = _rule_based_recommend(season, calamity_type)
        ranked = [
            CropRank(
                rank=i + 1,
                crop=r["crop"],
                confidence=r["confidence"],
                reason=CROP_REASONS.get(r["crop"], "Well-suited to local conditions"),
            )
            for i, r in enumerate(raw)
        ]

    auto_info = AutoDetectedInfo(
        season=season,
        temperature=weather["temperature"],
        humidity=weather["humidity"],
        rainfall=weather.get("rainfall", 0.0),
        weather_condition=weather["condition"],
        recent_calamity=calamity_type,
        calamity_source=calamity_source,
        soil_N=soil["N"],
        soil_P=soil["P"],
        soil_K=soil["K"],
        soil_ph=soil["ph"],
    )

    advisory = CALAMITY_ADVISORIES.get(
        calamity_type,
        "Adjust crop choice based on local extension advisories and current market demand.",
    )

    return CropRecommendResponse(
        location=location,
        auto_detected=auto_info,
        top_crops=ranked,
        advisory=advisory,
    )
