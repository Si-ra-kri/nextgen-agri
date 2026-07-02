"""
routes/schemes.py
POST /api/schemes/find  — government scheme eligibility checker

Database of schemes for India, Kenya, Ethiopia, Vietnam, Brazil.
Uses a simple rule engine (region + farm size + income + crops).
All data is curated from public government sources (2024-2025).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


# ── Pydantic request model ────────────────────────────────────────────────────
class SchemesRequest(BaseModel):
    region: str = Field(..., description="Country or region (e.g. india, kenya, ethiopia, vietnam, brazil)")
    farm_size_ha: float = Field(..., ge=0.1, le=500, description="Farm size in hectares")
    crops: list[str] = Field(default=[], description="Crops being grown")
    annual_income_usd: Optional[float] = Field(default=None, description="Annual household income in USD")


# ── Scheme database ───────────────────────────────────────────────────────────
# Each scheme: id, name, country, description, benefit_usd, deadline,
#              eligibility: { max_ha, min_ha, crops (None=any), max_income_usd }

SCHEMES: list[dict] = [

    # ─────── INDIA ─────────────────────────────────────────────────────────────
    {
        "id": "IN_PMKISAN",
        "country": "india",
        "name": "PM-Kisan Samman Nidhi",
        "description": "Direct income support of ₹6,000/year (≈$72) to all smallholder families owning farmland.",
        "benefit_usd": 72,
        "benefit_display": "₹6,000/year (~$72)",
        "type": "income_support",
        "deadline": "Ongoing — enrol anytime at pmkisan.gov.in",
        "apply_url": "https://pmkisan.gov.in",
        "eligibility": {"max_ha": None, "min_ha": None, "crops": None, "max_income_usd": None},
    },
    {
        "id": "IN_PMFBY",
        "country": "india",
        "name": "Pradhan Mantri Fasal Bima Yojana (Crop Insurance)",
        "description": "Comprehensive crop insurance covering losses due to drought, flood, pest, and disease. Premium: 1.5–2% of sum insured.",
        "benefit_usd": 3500,
        "benefit_display": "Up to ₹2.9 lakh (~$3,500) per claim",
        "type": "insurance",
        "deadline": "Kharif: June 30 | Rabi: Dec 31",
        "apply_url": "https://pmfby.gov.in",
        "eligibility": {"max_ha": None, "min_ha": None, "crops": None, "max_income_usd": None},
    },
    {
        "id": "IN_PMKSY",
        "country": "india",
        "name": "PM Krishi Sinchayee Yojana (Drip Irrigation Subsidy)",
        "description": "Government subsidises 55–90% of drip/sprinkler irrigation installation costs. Saves 40–50% water.",
        "benefit_usd": 1800,
        "benefit_display": "55–90% subsidy on drip system (~$1,800 avg)",
        "type": "infrastructure",
        "deadline": "Apply via district agriculture office",
        "apply_url": "https://pmksy.gov.in",
        "eligibility": {"max_ha": 5, "min_ha": None, "crops": None, "max_income_usd": None},
    },
    {
        "id": "IN_KISAN_CREDIT",
        "country": "india",
        "name": "Kisan Credit Card (KCC)",
        "description": "Short-term agricultural credit at 4–7% interest for seeds, fertilisers, and other inputs.",
        "benefit_usd": 5000,
        "benefit_display": "Up to ₹3 lakh (~$3,600) credit at 4% interest",
        "type": "credit",
        "deadline": "Ongoing — apply at any nationalised bank",
        "apply_url": "https://nabard.org/kcc",
        "eligibility": {"max_ha": None, "min_ha": None, "crops": None, "max_income_usd": None},
    },

    # ─────── KENYA ──────────────────────────────────────────────────────────────
    {
        "id": "KE_KCSA",
        "country": "kenya",
        "name": "Kenya Climate Smart Agriculture Programme",
        "description": "Supports smallholders with subsidised drought-tolerant seeds, drip irrigation, and farmer training.",
        "benefit_usd": 800,
        "benefit_display": "Ksh 80,000 (~$800) in inputs + training",
        "type": "infrastructure",
        "deadline": "31 October 2026",
        "apply_url": "https://kilimo.go.ke",
        "eligibility": {"max_ha": 5, "min_ha": None, "crops": None, "max_income_usd": 3000},
    },
    {
        "id": "KE_NLPIS",
        "country": "kenya",
        "name": "National Livestock & Plant Insurance Scheme",
        "description": "Index-based agricultural insurance covering drought-related crop loss. Premium: 3.5% of insured value.",
        "benefit_usd": 2000,
        "benefit_display": "Up to Ksh 200,000 (~$2,000) per claim",
        "type": "insurance",
        "deadline": "Enrolment: Jan–Feb and Jul–Aug",
        "apply_url": "https://agriculture.go.ke",
        "eligibility": {"max_ha": 10, "min_ha": None, "crops": None, "max_income_usd": None},
    },
    {
        "id": "KE_INPUT_SUBSIDY",
        "country": "kenya",
        "name": "National Fertiliser Subsidy Programme",
        "description": "50% government subsidy on certified fertilisers through registered agro-dealers.",
        "benefit_usd": 120,
        "benefit_display": "50% off fertilisers — ~$120 savings/ha",
        "type": "input_subsidy",
        "deadline": "Seasonal — apply at local sub-county office",
        "apply_url": "https://kilimo.go.ke/fertilizer",
        "eligibility": {"max_ha": 5, "min_ha": None, "crops": None, "max_income_usd": None},
    },

    # ─────── ETHIOPIA ────────────────────────────────────────────────────────────
    {
        "id": "ET_PSNP",
        "country": "ethiopia",
        "name": "Productive Safety Net Programme (PSNP)",
        "description": "Food-insecure rural households receive cash or food transfers in exchange for public works participation.",
        "benefit_usd": 180,
        "benefit_display": "~ETB 9,500/year (~$180) cash or food-equivalent",
        "type": "social_protection",
        "deadline": "Ongoing — enrol via Woreda Agriculture Office",
        "apply_url": "https://www.moa.gov.et",
        "eligibility": {"max_ha": 2, "min_ha": None, "crops": None, "max_income_usd": 500},
    },
    {
        "id": "ET_ADLI",
        "country": "ethiopia",
        "name": "Agricultural Development-Led Industrialisation (ADLI) Input Package",
        "description": "Subsidised improved seed and fertiliser packages for smallholders to boost productivity.",
        "benefit_usd": 150,
        "benefit_display": "Subsidised inputs valued at ~$150/ha",
        "type": "input_subsidy",
        "deadline": "Before planting season — apply at Woreda office",
        "apply_url": "https://www.moa.gov.et",
        "eligibility": {"max_ha": 5, "min_ha": None, "crops": None, "max_income_usd": None},
    },

    # ─────── VIETNAM ────────────────────────────────────────────────────────────
    {
        "id": "VN_AGRI_SUPPORT",
        "country": "vietnam",
        "name": "Vietnam Agricultural Support Policy (Decree 57/2018)",
        "description": "Subsidises investment in agricultural machinery, high-tech greenhouses, and certified seed production.",
        "benefit_usd": 2500,
        "benefit_display": "Up to VND 60M (~$2,500) machinery subsidy",
        "type": "infrastructure",
        "deadline": "Apply at provincial DARD before Q3 each year",
        "apply_url": "https://mard.gov.vn",
        "eligibility": {"max_ha": 10, "min_ha": None, "crops": None, "max_income_usd": None},
    },
    {
        "id": "VN_CROP_INSURANCE",
        "country": "vietnam",
        "name": "Vietnam Agricultural Insurance Pilot (Decree 58)",
        "description": "Government pays 90–100% of insurance premium for poor/near-poor farmers. Covers weather, disease, and pest losses.",
        "benefit_usd": 1200,
        "benefit_display": "Free insurance for poor farmers; claim up to $1,200",
        "type": "insurance",
        "deadline": "Enrol before crop season start",
        "apply_url": "https://mard.gov.vn/insurance",
        "eligibility": {"max_ha": 3, "min_ha": None, "crops": ["rice", "maize", "sugarcane", "pepper", "rubber", "cassava", "cashew"], "max_income_usd": 2000},
    },

    # ─────── BRAZIL ─────────────────────────────────────────────────────────────
    {
        "id": "BR_PRONAF",
        "country": "brazil",
        "name": "PRONAF (Family Agriculture Strengthening Programme)",
        "description": "Subsidised rural credit at 3–6% interest per year for smallholder family farmers to invest in production and infrastructure.",
        "benefit_usd": 6000,
        "benefit_display": "Up to R$50,000 (~$9,500) at 3% interest/year",
        "type": "credit",
        "deadline": "Ongoing — apply at BNDES, Banco do Brasil, or Sicoob",
        "apply_url": "https://www.gov.br/agricultura/pronaf",
        "eligibility": {"max_ha": 4, "min_ha": None, "crops": None, "max_income_usd": 18000},
    },
    {
        "id": "BR_PSR",
        "country": "brazil",
        "name": "Rural Insurance Premium Subsidy Programme (PSR)",
        "description": "Government co-pays 30–70% of agricultural insurance premium for family farmers.",
        "benefit_usd": 900,
        "benefit_display": "30–70% premium subsidy — save up to $900/season",
        "type": "insurance",
        "deadline": "Before crop sowing — apply via Mapa portal",
        "apply_url": "https://www.gov.br/agricultura/psr",
        "eligibility": {"max_ha": 4, "min_ha": None, "crops": None, "max_income_usd": None},
    },
]


def _norm(s: str) -> str:
    return s.strip().lower().replace("-", " ").replace("_", " ")


def _check_eligible(scheme: dict, region: str, farm_ha: float, crops: list[str], income: Optional[float]) -> bool:
    el = scheme["eligibility"]
    country = scheme["country"]

    # Region match (flexible — india matches all scheme countries that contain india)
    region_norm = _norm(region)
    country_norm = _norm(country)
    if country_norm not in region_norm and region_norm not in country_norm:
        # Also check common aliases
        aliases = {
            "south asia": ["india", "pakistan", "bangladesh"],
            "sub saharan": ["kenya", "ethiopia", "uganda", "tanzania"],
            "sub-saharan africa": ["kenya", "ethiopia", "uganda", "tanzania"],
            "africa": ["kenya", "ethiopia", "uganda", "tanzania"],
            "southeast asia": ["vietnam", "philippines", "cambodia", "thailand"],
            "latin america": ["brazil", "mexico", "colombia"],
        }
        match = False
        for alias_key, countries in aliases.items():
            if alias_key in region_norm and country_norm in countries:
                match = True
                break
        if not match:
            return False

    # Farm size
    if el.get("min_ha") is not None and farm_ha < el["min_ha"]:
        return False
    if el.get("max_ha") is not None and farm_ha > el["max_ha"]:
        return False

    # Income
    if el.get("max_income_usd") is not None and income is not None:
        if income > el["max_income_usd"]:
            return False

    # Crops
    if el.get("crops"):
        # At least one of farmer's crops must match scheme's allowed crops
        farmer_crops_norm = {_norm(c) for c in crops}
        scheme_crops_norm = {_norm(c) for c in el["crops"]}
        if not farmer_crops_norm.intersection(scheme_crops_norm):
            return False

    return True


def _days_until_deadline(deadline_str: str) -> Optional[int]:
    """Try to parse the deadline and compute days remaining."""
    import re
    today = date.today()
    # Try to find a date pattern like "31 October 2026" or "Dec 31"
    patterns = [
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",   # 31 October 2026
        r"([A-Za-z]+)\s+(\d{1,2})",              # Oct 31  / Dec 31 (no year)
    ]
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    try:
        m = re.search(patterns[0], deadline_str, re.IGNORECASE)
        if m:
            day  = int(m.group(1))
            mon  = months.get(m.group(2)[:3].lower())
            year = int(m.group(3))
            if mon:
                deadline_date = date(year, mon, day)
                return (deadline_date - today).days
    except Exception:
        pass
    return None


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/find")
async def find_schemes(req: SchemesRequest):
    """
    Find all government schemes the farmer is eligible for.
    Returns eligible schemes, total potential benefit, and eligibility flags.
    """
    eligible   = []
    ineligible = []

    for scheme in SCHEMES:
        is_el = _check_eligible(
            scheme, req.region, req.farm_size_ha,
            req.crops, req.annual_income_usd
        )
        days_left = _days_until_deadline(scheme["deadline"])
        entry = {
            "id":             scheme["id"],
            "name":           scheme["name"],
            "description":    scheme["description"],
            "benefit_usd":    scheme["benefit_usd"],
            "benefit_display":scheme["benefit_display"],
            "type":           scheme["type"],
            "deadline":       scheme["deadline"],
            "apply_url":      scheme["apply_url"],
            "days_until_deadline": days_left,
            "urgent": days_left is not None and days_left <= 45,
        }
        if is_el:
            eligible.append(entry)
        else:
            ineligible.append(entry)

    total_benefit = sum(s["benefit_usd"] for s in eligible)
    income_mult   = (
        round(total_benefit / req.annual_income_usd, 1)
        if req.annual_income_usd and req.annual_income_usd > 0
        else None
    )

    return {
        "region":             req.region,
        "farm_size_ha":       req.farm_size_ha,
        "eligible_schemes":   eligible,
        "ineligible_schemes": ineligible,
        "total_eligible":     len(eligible),
        "total_benefit_usd":  total_benefit,
        "income_multiplier":  income_mult,
        "message": (
            f"You qualify for {len(eligible)} scheme(s) worth up to ${total_benefit:,.0f}."
            if eligible else
            "No matching schemes found. Try adjusting your region or farm details."
        ),
    }
