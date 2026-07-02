"""
routes/community.py
POST /api/community/log    — anonymous farmer activity log (no personal data)
GET  /api/community/stats  — aggregated community usage stats

Every time a farmer uses any pillar, an anonymous entry is stored in
backend/data/activity.json. In production this feeds a vector DB for
semantic search, regional clustering, and personalised alerts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

DATA_DIR      = Path(__file__).parent.parent / "data"
ACTIVITY_FILE = DATA_DIR / "activity.json"
DATA_DIR.mkdir(exist_ok=True)
MAX_ACTIVITY  = 5000


def _load() -> list[dict]:
    if ACTIVITY_FILE.exists():
        try:
            d = json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
            if isinstance(d, list):
                return d
        except Exception:
            pass
    return []


def _save(log: list[dict]) -> None:
    try:
        ACTIVITY_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


ACTIVITY_LOG: list[dict] = _load()


class ActivityEntry(BaseModel):
    type:         str            # irrigation | disease_check | crop_recommend | pricing | schemes
    crop:         Optional[str] = None
    region:       Optional[str] = None
    season:       Optional[str] = None
    disease:      Optional[str] = None
    result_count: Optional[int] = None


@router.post("/log")
async def log_activity(entry: ActivityEntry):
    """Anonymously log a farmer interaction for community analytics."""
    record = entry.model_dump(exclude_none=True)
    record["ts"] = datetime.now(timezone.utc).isoformat()
    ACTIVITY_LOG.append(record)
    if len(ACTIVITY_LOG) > MAX_ACTIVITY:
        del ACTIVITY_LOG[: len(ACTIVITY_LOG) - MAX_ACTIVITY]
    _save(ACTIVITY_LOG)
    return {"logged": True, "total": len(ACTIVITY_LOG)}


@router.get("/stats")
async def get_stats():
    """Return aggregated (anonymous) community usage statistics."""
    from collections import Counter
    recent = ACTIVITY_LOG[-1000:] if len(ACTIVITY_LOG) > 1000 else ACTIVITY_LOG
    return {
        "total_farmer_sessions": len(ACTIVITY_LOG),
        "features_used":    dict(Counter(e["type"]   for e in recent).most_common(6)),
        "popular_crops":    dict(Counter(e["crop"]   for e in recent if e.get("crop")).most_common(5)),
        "active_regions":   dict(Counter(e["region"] for e in recent if e.get("region")).most_common(5)),
        "diseases_detected":dict(Counter(e["disease"]for e in recent if e.get("disease")).most_common(5)),
    }
