"""
NextGen Agri - FastAPI Backend
main.py: App entry point, middleware, model loader, router registration
"""

import os
import time
import logging
from contextlib import asynccontextmanager

import joblib
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = os.getenv("MODEL_DIR", "./models")

# ─────────────────────────────────────────────
# Lifespan: load models ONCE at startup
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all ML models into app.state at startup."""
    logger.info("Loading ML models …")

    # Irrigation model (Random Forest Regressor)
    irr_path = os.path.join(MODEL_DIR, "irrigation_model.pkl")
    if os.path.exists(irr_path):
        app.state.irrigation_model = joblib.load(irr_path)
        logger.info("✅ irrigation_model.pkl loaded")
    else:
        app.state.irrigation_model = None
        logger.warning("⚠️  irrigation_model.pkl not found — rule-based fallback active")

    # Crop recommendation model (Random Forest Classifier)
    # Saved as a bundle: {"model": RFC, "classes": [crop_names...]}
    rec_path = os.path.join(MODEL_DIR, "recommend_model.pkl")
    if os.path.exists(rec_path):
        bundle = joblib.load(rec_path)
        if isinstance(bundle, dict):
            app.state.recommend_model = bundle.get("model")
            app.state.recommend_classes = bundle.get("classes", [])
        else:
            app.state.recommend_model = bundle
            app.state.recommend_classes = []
        logger.info("✅ recommend_model.pkl loaded")
    else:
        app.state.recommend_model = None
        app.state.recommend_classes = []
        logger.warning("⚠️  recommend_model.pkl not found — rule-based fallback active")

    # Disease CNN model (TensorFlow / Keras .h5)
    dis_path = os.path.join(MODEL_DIR, "disease_model.h5")
    if os.path.exists(dis_path):
        try:
            from tensorflow import keras  # type: ignore
            app.state.disease_model = keras.models.load_model(dis_path)
            logger.info("✅ disease_model.h5 loaded")
        except ImportError:
            app.state.disease_model = None
            logger.warning("⚠️  TensorFlow not installed — disease detection uses rule-based fallback")
    else:
        app.state.disease_model = None
        logger.warning("⚠️  disease_model.h5 not found — rule-based fallback active")

    yield  # server is running

    logger.info("Shutting down NextGen Agri backend …")


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title="NextGen Agri API",
    description="AI-powered precision agriculture — Irrigation, Crop Health, Crop Recommendation, Market Pricing, Government Schemes, Real Forecast & Soil Data",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "null",          # file:// origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request logging middleware
# ─────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.1f}ms)")
    return response


# ─────────────────────────────────────────────
# Global error handler — consistent error shape
# ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": str(exc), "code": 500},
    )


# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────
from routes.irrigation import router as irrigation_router        # noqa: E402
from routes.crop_health import router as health_router           # noqa: E402
from routes.crop_recommend import router as recommend_router     # noqa: E402
from routes.pricing import router as pricing_router              # noqa: E402
from routes.schemes import router as schemes_router              # noqa: E402
from routes.forecast import router as forecast_router            # noqa: E402
from routes.soil import router as soil_router                    # noqa: E402
from routes.community import router as community_router          # noqa: E402
from utils.weather import router as weather_router               # noqa: E402
from utils.calamity import router as calamity_router             # noqa: E402

app.include_router(irrigation_router, prefix="/api/irrigation", tags=["Irrigation"])
app.include_router(health_router,     prefix="/api/health",     tags=["Crop Health"])
app.include_router(recommend_router,  prefix="/api/recommend",  tags=["Crop Recommendation"])
app.include_router(pricing_router,    prefix="/api/pricing",    tags=["Market Pricing"])
app.include_router(schemes_router,    prefix="/api/schemes",    tags=["Government Schemes"])
app.include_router(forecast_router,   prefix="/api",            tags=["Forecast & Geocoding"])
app.include_router(soil_router,       prefix="/api",            tags=["Soil Data"])
app.include_router(community_router,  prefix="/api/community",  tags=["Community"])
app.include_router(weather_router,    prefix="/api",            tags=["Weather"])
app.include_router(calamity_router,   prefix="/api",            tags=["Calamity"])


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
