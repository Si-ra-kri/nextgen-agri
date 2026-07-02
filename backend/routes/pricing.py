"""
routes/pricing.py
GET  /api/pricing/commodity   — live commodity price + 30-day trend + recommendation
GET  /api/pricing/buyers      — direct buyer directory by crop + region

All data is deterministic-mock (seeded by crop + date) so the hackathon demo
works without any external API keys.  Swap in real APIs (NCDEX, Yahoo Finance,
Agritech) by replacing the _mock_price / _mock_trend helpers.
"""

import math
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()

# ── Commodity base prices (USD / ton, rough 2024-2025 averages) ───────────────
COMMODITY_BASE: dict[str, float] = {
    "rice":      420.0,
    "wheat":     230.0,
    "maize":     200.0,
    "sorghum":   190.0,
    "millet":    210.0,
    "tomato":    310.0,
    "cassava":   160.0,
    "cocoa":    2800.0,
    "coffee":   3200.0,
    "cotton":    950.0,
    "soybean":   470.0,
    "sugarcane":  38.0,
    "potato":    180.0,
    "onion":     220.0,
    "banana":    290.0,
}

# Regional price multipliers  (local market vs. global spot)
REGION_MULT: dict[str, float] = {
    "india":           1.05,
    "south_asia":      1.05,
    "africa":          0.92,
    "sub_saharan":     0.92,
    "southeast_asia":  0.98,
    "latin_america":   0.95,
    "middle_east":     1.10,
    "default":         1.00,
}

# Middleman discount a farmer actually receives (% of market price)
FARM_GATE_PCT: dict[str, float] = {
    "rice": 0.62, "wheat": 0.65, "maize": 0.60, "sorghum": 0.58,
    "millet": 0.60, "tomato": 0.55, "cassava": 0.52, "cocoa": 0.30,
    "coffee": 0.28, "cotton": 0.68, "soybean": 0.66, "sugarcane": 0.70,
    "potato": 0.58, "onion": 0.50, "banana": 0.55,
}

# Seasonal peak months (1-12) — prices typically rise
SEASONAL_PEAKS: dict[str, list[int]] = {
    "rice":      [2, 3, 8, 9],
    "wheat":     [5, 6],
    "maize":     [3, 4, 9],
    "tomato":    [12, 1, 2],
    "onion":     [11, 12, 1],
    "potato":    [3, 4],
    "default":   [3, 9],
}

# Direct buyer archetypes per crop
BUYER_DB: dict[str, list[dict]] = {
    "rice":     [{"name": "RiceLink Co-op",       "price_premium_pct": 12, "min_tons": 2,  "contact": "+254-700-RICE"},
                 {"name": "AgroCorp Export",        "price_premium_pct": 18, "min_tons": 10, "contact": "agrocorp@email.com"}],
    "wheat":    [{"name": "FlourMill Direct",      "price_premium_pct": 14, "min_tons": 5,  "contact": "+91-98-WHEAT"},
                 {"name": "Bread & Co. Bakeries",   "price_premium_pct": 10, "min_tons": 2,  "contact": "buy@breadco.in"}],
    "maize":    [{"name": "FeedStock Alliance",    "price_premium_pct": 15, "min_tons": 3,  "contact": "+255-MAIZE"},
                 {"name": "Ethanol Processing Ltd.", "price_premium_pct": 20, "min_tons": 20, "contact": "procurement@epltd.co"}],
    "tomato":   [{"name": "FreshMart Regional",   "price_premium_pct": 20, "min_tons": 1,  "contact": "+254-FM-TOMS"},
                 {"name": "Smoothie Factory",      "price_premium_pct": 30, "min_tons": 5,  "contact": "buy@smoothiefactory.com"},
                 {"name": "Local Veg Co-op",        "price_premium_pct": 16, "min_tons": 0.5,"contact": "+91-VEG-COOP"}],
    "cocoa":    [{"name": "ChocoDirect Belgium",  "price_premium_pct": 45, "min_tons": 1,  "contact": "cacao@chocodirect.be"},
                 {"name": "FairChoc Network",       "price_premium_pct": 60, "min_tons": 0.5,"contact": "fair@fairchoc.org"}],
    "coffee":   [{"name": "SpecialtyCup Roasters","price_premium_pct": 80, "min_tons": 0.2,"contact": "green@specialtycup.com"},
                 {"name": "EthicaBrew Co-op",       "price_premium_pct": 70, "min_tons": 0.5,"contact": "buy@ethicabrew.com"}],
    "default":  [{"name": "AgriConnect Hub",       "price_premium_pct": 12, "min_tons": 1,  "contact": "hello@agriconnect.app"},
                 {"name": "FarmerFirst Market",    "price_premium_pct": 18, "min_tons": 2,  "contact": "buy@farmerfirst.io"}],
}

# Storage tips per crop
STORAGE_TIPS: dict[str, str] = {
    "rice":     "Store in cool, dry place (< 15 °C, < 14% moisture). Hermetic bags extend shelf life to 12 months.",
    "wheat":    "Dry to < 12% moisture before storage. Sealed silos prevent pest damage.",
    "tomato":   "Keep at 13–18 °C, 85–90% humidity. Do NOT refrigerate unripe tomatoes.",
    "onion":    "Store at 3–5 °C in well-ventilated crates. Avoid moisture to prevent rot.",
    "potato":   "Store at 4–8 °C in darkness. Exposure to light causes greening and solanine buildup.",
    "maize":    "Dry to < 13.5% moisture. Aflatoxin risk if stored wet — use hermetic bags.",
    "cocoa":    "Ferment 5–7 days post-harvest, dry to 7.5% moisture. Jute bags, good airflow.",
    "coffee":   "Parchment stage storage at 11% moisture. GrainPro bags preserve quality up to 18 months.",
    "default":  "Keep in cool, dry, ventilated conditions. Check regularly for mold and pest activity.",
}


def _norm_crop(crop: str) -> str:
    return crop.strip().lower().replace(" ", "_")


def _norm_region(region: str) -> str:
    r = region.strip().lower().replace(" ", "_").replace("-", "_")
    for key in REGION_MULT:
        if key in r:
            return key
    return "default"


def _day_seed(crop: str) -> float:
    """Deterministic daily variation seeded by crop name + today's date."""
    today = date.today()
    seed_str = f"{crop}{today.year}{today.month}{today.day}"
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(seed_str))
    return (seed % 1000) / 1000.0  # 0.0 – 0.999


def _mock_price(crop: str, region: str) -> float:
    base = COMMODITY_BASE.get(crop, 250.0)
    mult = REGION_MULT.get(region, 1.0)
    variation = 0.92 + _day_seed(crop) * 0.16   # ±8% daily swing
    return round(base * mult * variation, 2)


def _mock_trend(crop: str, region: str) -> list[float]:
    """Generate 30-day price history ending at today's price."""
    today_price = _mock_price(crop, region)
    seed = _day_seed(crop)
    trend = []
    for i in range(30):
        days_ago = 29 - i
        wave = math.sin((seed * 6.28) + days_ago * 0.4) * 0.06   # ±6% sinusoidal
        noise = ((seed * 17 + days_ago * 3) % 100) / 1000 - 0.05  # ±5% noise
        factor = 1.0 + wave + noise
        trend.append(round(today_price * factor, 2))
    trend.append(today_price)   # index 30 = today
    return trend


def _price_forecast(crop: str, trend: list[float]) -> dict:
    """Simple momentum forecast: last-7-day slope → next-3-week prediction."""
    recent = trend[-8:]
    slope = (recent[-1] - recent[0]) / 7       # $/ton per day
    forecast_3w = trend[-1] + slope * 21
    pct_change = round((forecast_3w - trend[-1]) / trend[-1] * 100, 1)

    if pct_change > 8:
        rec = "HOLD — prices forecast to rise {pct}% in 3 weeks. Store if possible.".format(pct=abs(pct_change))
        action = "hold"
    elif pct_change < -8:
        rec = "SELL NOW — prices forecast to drop {pct}% in 3 weeks.".format(pct=abs(pct_change))
        action = "sell"
    else:
        rec = "NEUTRAL — prices expected to remain stable. Sell at your convenience."
        action = "neutral"

    return {
        "forecast_usd_per_ton": round(forecast_3w, 2),
        "forecast_pct_change": pct_change,
        "recommendation": rec,
        "action": action,
    }


def _peak_info(crop: str) -> dict:
    today_month = date.today().month
    peaks = SEASONAL_PEAKS.get(crop, SEASONAL_PEAKS["default"])
    months_to_peak = min(
        ((p - today_month) % 12) for p in peaks
    )
    if months_to_peak == 0:
        note = "Peak season NOW — best time to sell."
    elif months_to_peak <= 2:
        note = f"Seasonal peak in ~{months_to_peak} month(s). Consider short-term storage."
    else:
        note = f"Next seasonal peak is ~{months_to_peak} months away."
    return {"months_to_peak": months_to_peak, "note": note}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/commodity")
async def get_commodity_price(
    crop: str = Query(..., description="Crop name (e.g. rice, tomato, wheat)"),
    region: str = Query("default", description="Region (india, africa, southeast_asia …)"),
):
    """
    Returns current commodity price, 30-day trend, forecast, farm-gate price,
    seasonal peak info, storage tips.
    """
    crop_key   = _norm_crop(crop)
    region_key = _norm_region(region)

    current_price  = _mock_price(crop_key, region_key)
    trend_30d      = _mock_trend(crop_key, region_key)
    forecast       = _price_forecast(crop_key, trend_30d)
    farm_gate_pct  = FARM_GATE_PCT.get(crop_key, 0.60)
    farm_gate      = round(current_price * farm_gate_pct, 2)
    middleman_loss = round(current_price - farm_gate, 2)
    peak_info      = _peak_info(crop_key)
    storage        = STORAGE_TIPS.get(crop_key, STORAGE_TIPS["default"])

    # 30-day low / high
    price_30d_low  = round(min(trend_30d), 2)
    price_30d_high = round(max(trend_30d), 2)

    return {
        "crop": crop,
        "region": region,
        "current_price_usd_per_ton": current_price,
        "farm_gate_price_usd_per_ton": farm_gate,
        "middleman_extraction_usd_per_ton": middleman_loss,
        "farm_gate_pct": round(farm_gate_pct * 100, 0),
        "trend_30d": trend_30d,
        "price_30d_low": price_30d_low,
        "price_30d_high": price_30d_high,
        "forecast": forecast,
        "seasonal_peak": peak_info,
        "storage_tip": storage,
    }


@router.get("/buyers")
async def get_buyers(
    crop: str = Query(..., description="Crop name"),
    region: str = Query("default", description="Region"),
):
    """Returns direct buyer directory for a crop + region."""
    crop_key = _norm_crop(crop)
    buyers   = BUYER_DB.get(crop_key, BUYER_DB["default"])

    # Attach absolute prices
    base_price = _mock_price(crop_key, _norm_region(region))
    enriched   = []
    for b in buyers:
        premium = b["price_premium_pct"]
        buyer_price = round(base_price * (1 + premium / 100), 2)
        enriched.append({**b, "offer_price_usd_per_ton": buyer_price})

    return {
        "crop": crop,
        "region": region,
        "market_price_usd_per_ton": base_price,
        "buyers": enriched,
        "tip": (
            "Direct buyers pay 10–80% more than local middlemen. "
            "Contact them before harvest to pre-arrange sale."
        ),
    }
