# CyberLens v3.0 — Criminal Intelligence Platform

> AI-powered cybercrime detection & intelligence platform built for **Gurugram Police / GPCSSI India**.

---

## 🚀 Features

| Module | Description |
|---|---|
| **Scam Classifier** | 14-category DistilBERT model — classifies UPI fraud, fake KYC, sextortion, etc. |
| **Deepfake Detector** | Image-based deepfake detection with intent analysis & legal mapping |
| **OCR Engine** | Hindi + English multi-engine OCR with entity extraction (UPI IDs, phone numbers) |
| **Criminal Network Graph** | Neo4j-backed relationship mapping across suspects, accounts, and channels |
| **Intelligence Pipeline** | Evidence-based attribution, confidence scoring, and analyst recommendations |
| **Real-time Monitor** | Telegram/social media channel monitoring with alert escalation |
| **Template Fingerprinting** | Perceptual hash-based scam template matching and viral spread tracking |
| **OSINT Enrichment** | Safe Browsing, WHOIS, and multi-source intelligence gathering |
| **FIR Generation** | Automated First Information Report generation with IPC/IT Act mapping |
| **Model Evaluation** | Precision/recall/F1 dashboards with confusion matrices |
| **I4C Integration** | National Cybercrime Reporting Portal submission API |

---

## 📁 Project Structure

```
cyberlens/
├── frontend/          # React + Vite dashboard (deployed to Vercel)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/api.js
│   ├── vercel.json
│   └── vite.config.js
├── src/               # FastAPI backend (deployed to Render)
│   ├── api/           # Routes & background workers
│   ├── classifier/    # Scam classifier model
│   ├── deepfake/      # Deepfake detector + intent analyzer
│   ├── intelligence/  # Attribution, confidence, recommendations
│   ├── crawler/       # Social media scraping
│   ├── graph/         # Neo4j client
│   ├── ocr/           # OCR engines
│   ├── monitor/       # Real-time channel monitoring
│   └── fingerprinting/
├── scripts/           # Training & evaluation scripts
├── configs/           # Category definitions (YAML)
├── models/            # Trained model weights (gitignored)
├── data/              # Datasets & DB (gitignored)
├── render.yaml        # Render deployment blueprint
└── requirements.txt   # Python dependencies
```

---

## 🛠️ Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) Neo4j 5.x for graph features

### Backend
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# Start the API server
uvicorn src.api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → opens at http://localhost:3000
```

### Train ML Models (Optional)
```bash
# Generate training dataset
python scripts/generate_dataset.py

# Train scam classifier
python scripts/train_classifier.py

# Train deepfake detector
python scripts/train_deepfake.py

# Evaluate all models
python scripts/evaluate_all_models.py
```

---

## ☁️ Deployment

### Frontend → Vercel

1. Push this repo to GitHub
2. Go to [vercel.com/new](https://vercel.com/new) → Import the repo
3. Set **Root Directory** to `frontend`
4. Set **Build Command** to `npm run build`
5. Set **Output Directory** to `dist`
6. Add environment variable:
   - `VITE_API_URL` = `https://your-render-backend.onrender.com/api`
7. Deploy

### Backend → Render

1. Go to [render.com](https://render.com) → **New Web Service**
2. Connect this GitHub repo
3. Render will auto-detect `render.yaml` blueprint
4. Set environment variables in the dashboard:
   - `FRONTEND_URL` = `https://your-app.vercel.app`
   - `GEMINI_API_KEY` = your key
   - `MISTRAL_API_KEY` = your key (for OCR)
5. Deploy

> **Note:** The free Render tier has 512 MB RAM. For the full ML stack (PyTorch + Transformers), use the Starter plan ($7/mo).

---

## 🔑 Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLite connection string |
| `AUTH_DISABLED` | No | Set `false` in production to enforce JWT |
| `GEMINI_API_KEY` | No | Google Gemini for AI-powered analysis |
| `MISTRAL_API_KEY` | No | Mistral Vision for OCR |
| `NEO4J_URI` | No | Neo4j graph database URI |
| `FRONTEND_URL` | Prod | Vercel URL (for CORS) |
| `VITE_API_URL` | Prod | Render backend URL (frontend env) |

---

## 📜 License

Built for Gurugram Police Commissionerate's Cyber Security Summer Internship (GPCSSI).

---

## 👥 Team

**CyberLens Team** — GPCSSI Internship, Gurugram Police, India
