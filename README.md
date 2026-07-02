# 🌱 NextGen Agri — AI Precision Agriculture Platform

> **AI-powered crop health, irrigation, market prices, and government scheme access for 500M+ smallholder farmers globally.**

![NextGen Agri](https://img.shields.io/badge/NextGen%20Agri-v3.0.0-2d6a4f?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

---

## 🎯 Problem

- **719 million people** live on less than $1.90/day — 80% are rural farmers
- Farmers lose **30–40% of yield** to undetected crop disease every year
- **40–60% of irrigation water** is wasted through flood methods
- Middlemen extract **70–75%** of commodity price from farmers
- **$100B+** in government agricultural subsidies go unclaimed annually

## 💡 Solution

NextGen Agri is a full-stack AI platform with **5 precision agriculture pillars** — deployable across any region, climate, and crop globally. Works entirely with **free, keyless APIs**.

---

## 🏗️ Architecture

```
nextgen-agri/
├── backend/                  # FastAPI Python backend
│   ├── main.py               # App entry point, CORS, model loader
│   ├── routes/
│   │   ├── irrigation.py     # P1 — AI irrigation scheduling
│   │   ├── crop_health.py    # P2 — CNN disease detection
│   │   ├── crop_recommend.py # P3 — Crop recommendation engine
│   │   ├── pricing.py        # P4 — Market price intelligence
│   │   ├── schemes.py        # P5 — Government scheme eligibility
│   │   ├── forecast.py       # Open-Meteo 7-day weather forecast
│   │   ├── soil.py           # SoilGrids ISRIC real soil data
│   │   └── community.py      # Anonymous activity logging
│   ├── schemas/              # Pydantic request/response models
│   ├── utils/                # Image preprocessing, weather helpers
│   └── data/                 # Persisted JSON: outbreaks, activity
├── frontend/
│   ├── index.html            # Single-page app (vanilla HTML/CSS/JS)
│   └── assets/
│       └── sample-leaves/    # Sample leaf images for testing
└── README.md
```

---

## 🌟 5 Core Pillars

### 💧 Pillar 1 — Smart Irrigation
- Enter location + soil conditions
- Fetches **real 7-day weather** from Open-Meteo (free, no key)
- AI decides **irrigate vs skip** per day based on rain forecast
- Water savings calculator: litres saved, CO₂ offset, annual impact
- Shareable impact report via Web Share API / clipboard

### 🔬 Pillar 2 — Disease Detection
- Upload any crop leaf photo (JPEG/PNG)
- CNN model (MobileNetV2) identifies: **Healthy, Fungi/Blight, Bacterial Spot, Insect Damage, Rust, Mosaic Virus**
- Returns exact **pesticide name, dosage (ml/L), coverage area**
- Every detection anonymously logged to **community outbreak tracker** (persisted to disk)
- Rule-based fallback when model file is absent

### 🌾 Pillar 3 — Crop Recommendation
- Enter location → everything else is automatic
- **Real soil data** (pH, N, clay %, sand %, organic carbon) from SoilGrids ISRIC
- Live weather via Open-Meteo geocoding
- Season auto-detected (Kharif / Rabi / Zaid)
- Calamity news scan — avoids flood-prone crops during drought alerts
- AI ranks top 5 crops with confidence scores and planting advisories

### 📈 Pillar 4 — Market Intelligence
- 30-day commodity price trend chart
- **SELL vs HOLD** recommendation with reasoning
- Direct buyer directory — skip the middlemen
- Post-harvest storage tips per crop

### 🏛️ Pillar 5 — Government Schemes
- Checks **12+ real government schemes** across India, Kenya, Ethiopia, Vietnam, Brazil
- PM-Kisan, PMFBY, PMKSY, PSNP, PSR, PRONAF and more
- Eligibility engine based on farm size, income, crops, and country
- Direct application links for each scheme

---

## 🆓 Free APIs Used (No Key Required)

| API | Purpose |
|---|---|
| [Open-Meteo](https://open-meteo.com) | 7-day weather forecast for any GPS coordinates (ECMWF models) |
| [SoilGrids ISRIC](https://www.isric.org/explore/soilgrids) | Global soil pH, nitrogen, clay %, sand %, organic carbon |
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | City name → lat/lon coordinates |
| [Nominatim (OpenStreetMap)](https://nominatim.org) | GPS coordinates → city/country name |
| Browser Geolocation API | Device GPS |
| Web Speech API | Voice-to-text location input |

### Optional (free signup)
| API | Purpose |
|---|---|
| OpenWeatherMap | Backup weather source |
| NewsAPI | Calamity news scan for crop recommender |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Modern browser (Chrome/Edge recommended for voice input)

### 1. Clone the repo
```bash
git clone https://github.com/Si-ra-kri/nextgen-agri.git
cd nextgen-agri
```

### 2. Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. (Optional) Set API keys in `.env`
```env
OPENWEATHER_API_KEY=your_key_here   # optional backup weather
NEWS_API_KEY=your_key_here          # optional calamity news
```

### 4. Start the backend
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Start the frontend
```bash
cd ..
python -m http.server 5500 --directory frontend
```

### 6. Open the app
```
http://localhost:5500
```

**API Docs (Swagger UI):** `http://127.0.0.1:8000/docs`

---

## 🤖 AI Chatbot

A floating **💬 Ask AI** button is available on every page. The assistant knows about all 5 pillars and can answer questions like:

- *"How does disease detection work?"*
- *"What crops should I plant in Kharif season?"*
- *"How is weather data fetched without an API key?"*
- *"What government schemes am I eligible for?"*

---

## 🎨 UI Features

- **Dark / Light theme** toggle (saved to localStorage)
- **📍 Detect** button — auto-fill location via GPS
- **🎤 Speak** button — voice input for location fields
- Auto-scroll to result after every analysis
- Community disease outbreak map (real-time, persisted to disk)
- Responsive layout for mobile and desktop

---

## 🗺️ Community Disease Tracker

Every disease detection (non-healthy) is:
1. Anonymously appended to `backend/data/outbreaks.json`
2. Aggregated by disease type with region and trend
3. Displayed in the **Community Disease Alerts** panel

Data persists across server restarts. Seed data covers 20 real-world regions across India, Kenya, Vietnam, Ethiopia, Brazil, and the Philippines.

---

## 📊 Projected Impact (Year 1 — 100,000 Farmers)

| Metric | Value |
|---|---|
| Income gain | **$50M+** via optimisation & fair pricing |
| Meals secured | **100M+** through 30–40% yield recovery |
| Water conserved | **5 billion m³** vs flood irrigation |
| CO₂ saved | **2M+ tonnes** equivalent |
| Govt. benefits unlocked | **$55K** average per farmer |

---

## 🧪 Testing Disease Detection

Sample leaf images are included in `frontend/assets/sample-leaves/`:

| File | Expected Result |
|---|---|
| `leaf_healthy_rice.png` | Healthy ✅ |
| `leaf_blight_tomato.png` | Fungi/Blight 🔴 |
| `leaf_rust_wheat.png` | Rust ⚠️ |
| `leaf_insect_damage.png` | Insect Damage ⚠️ |
| `leaf_mosaic_virus.png` | Mosaic Virus ⚠️ |

---

## 📁 Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/irrigation/predict` | AI irrigation schedule |
| POST | `/api/health/analyze` | Single leaf disease detection |
| GET | `/api/health/outbreaks` | Community outbreak data |
| POST | `/api/recommend/crop` | AI crop recommendation |
| GET | `/api/pricing/commodity` | Market price intelligence |
| GET | `/api/pricing/buyers` | Direct buyer directory |
| POST | `/api/schemes/find` | Government scheme eligibility |
| GET | `/api/forecast` | 7-day weather forecast |
| GET | `/api/soil` | Real soil data from SoilGrids |
| POST | `/api/community/log` | Anonymous activity logging |
| GET | `/api/community/stats` | Community usage statistics |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10, FastAPI, Uvicorn |
| ML Inference | TensorFlow/Keras (MobileNetV2), scikit-learn |
| HTTP Client | httpx (async) |
| Frontend | Vanilla HTML5, CSS3, JavaScript (ES2022) |
| Charts | Chart.js v4 |
| Fonts | Inter (Google Fonts) |
| Data | JSON file persistence (→ vector DB in production) |

---

## 📄 License

MIT License — free to use, modify, and deploy.

---

<div align="center">
  <strong>NextGen Agri</strong> — Built to empower 500 million smallholder farmers worldwide 🌍
</div>
