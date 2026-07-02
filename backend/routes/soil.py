"""
routes/soil.py
GET /api/soil?lat=&lon= — real soil properties from SoilGrids REST API (ISRIC)

No API key required. Covers the entire globe.
Returns: pH, nitrogen (mg/kg), clay %, sand %, organic carbon (g/kg), inferred soil type.
Falls back to region-based defaults if SoilGrids is slow or unavailable.
"""

import httpx
from fastapi import APIRouter, Query

router = APIRouter()

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES    = ["phh2o", "nitrogen", "clay", "sand", "soc"]

# ── Regional fallbacks (lat/lon range buckets) ────────────────────────────────
# Used when SoilGrids is unavailable or times out.
REGIONAL_DEFAULTS = [
    # (lat_min, lat_max, lon_min, lon_max, profile)
    (8,  37, 68,  97, {"ph":6.6,"nitrogen_mg_kg":70,"clay_pct":28,"sand_pct":38,"organic_carbon_gkg":8.5}),   # South Asia
    (-5, 8,  60,  97, {"ph":5.8,"nitrogen_mg_kg":55,"clay_pct":35,"sand_pct":30,"organic_carbon_gkg":12.0}),  # SE Asia
    (-35,15, 25,  50, {"ph":6.2,"nitrogen_mg_kg":60,"clay_pct":30,"sand_pct":35,"organic_carbon_gkg":10.0}),  # East/Central Africa
    (-5, 37, -80,-34, {"ph":5.5,"nitrogen_mg_kg":65,"clay_pct":40,"sand_pct":25,"organic_carbon_gkg":15.0}),  # South America
    (20, 55, -130,-60,{"ph":6.8,"nitrogen_mg_kg":85,"clay_pct":22,"sand_pct":42,"organic_carbon_gkg":18.0}),  # North America
    (35, 70, -10, 45, {"ph":7.0,"nitrogen_mg_kg":75,"clay_pct":25,"sand_pct":40,"organic_carbon_gkg":14.0}),  # Europe
]
DEFAULT_SOIL = {"ph":6.8,"nitrogen_mg_kg":72,"clay_pct":26,"sand_pct":40,"organic_carbon_gkg":11.0}


def _regional_default(lat: float, lon: float) -> dict:
    for la, lb, loa, lob, profile in REGIONAL_DEFAULTS:
        if la <= lat <= lb and loa <= lon <= lob:
            return profile
    return DEFAULT_SOIL


def _infer_soil_type(clay: float, sand: float) -> str:
    silt = max(0.0, 100.0 - clay - sand)
    if clay >= 40:
        return "Clay"
    if sand >= 70:
        return "Sandy"
    if clay >= 27 and sand <= 45:
        return "Clay Loam"
    if silt >= 50 and clay < 27:
        return "Silty Loam"
    if clay >= 18 and sand <= 65:
        return "Loam"
    return "Sandy Loam"


@router.get("/soil")
async def get_soil(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """
    Fetch real soil properties from SoilGrids ISRIC v2.0.
    Globally available, no API key.  Typical response time: 2–8 seconds.
    """
    params = [("lon", lon), ("lat", lat)]
    for p in PROPERTIES:
        params.append(("property", p))
    params.append(("depth", "0-5cm"))

    result: dict = {}
    source  = "SoilGrids ISRIC v2.0"

    try:
        async with httpx.AsyncClient(timeout=14.0) as client:
            resp = await client.get(SOILGRIDS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        layers = data.get("properties", {}).get("layers", [])
        for layer in layers:
            name   = layer.get("name", "")
            depths = layer.get("depths", [])
            if not depths:
                continue
            mean_val = depths[0].get("values", {}).get("mean")
            if mean_val is None:
                continue
            d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1

            if name == "phh2o":
                result["ph"] = round(mean_val / d_factor, 1)
            elif name == "nitrogen":
                # stored in cg/kg; 1 cg/kg = 10 mg/kg
                result["nitrogen_mg_kg"] = round(mean_val * 10 / d_factor, 1)
            elif name == "clay":
                # stored in g/kg (d_factor=10 → g/kg), then /10 → %
                result["clay_pct"] = round(mean_val / d_factor / 10, 1)
            elif name == "sand":
                result["sand_pct"] = round(mean_val / d_factor / 10, 1)
            elif name == "soc":
                # stored as dg/kg; /10 = g/kg
                result["organic_carbon_gkg"] = round(mean_val / d_factor, 2)

    except Exception:
        # Graceful fallback — still useful for demo
        result = _regional_default(lat, lon)
        source = "Regional estimate (SoilGrids unavailable)"

    # Fill any missing keys
    fallback = _regional_default(lat, lon)
    for k, v in fallback.items():
        if k not in result:
            result[k] = v

    clay = result.get("clay_pct", 26)
    sand = result.get("sand_pct", 40)
    result["soil_type"]  = _infer_soil_type(clay, sand)
    result["latitude"]   = lat
    result["longitude"]  = lon
    result["source"]     = source

    # Fertility assessment
    n = result.get("nitrogen_mg_kg", 70)
    ph = result.get("ph", 6.8)
    result["fertility_notes"] = []
    if n < 50:
        result["fertility_notes"].append("Low nitrogen — consider compost or urea application")
    elif n > 150:
        result["fertility_notes"].append("High nitrogen — reduce N-fertiliser this season")
    if ph < 5.5:
        result["fertility_notes"].append("Acidic soil — lime application recommended")
    elif ph > 7.8:
        result["fertility_notes"].append("Alkaline soil — sulphur or acidic organic matter helps")
    if not result["fertility_notes"]:
        result["fertility_notes"].append("Soil fertility looks adequate for most crops")

    return result
