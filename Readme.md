# 💊 RxCheck — Clinical Drug Interaction Safety Dashboard

**RxCheck** is a production-grade drug interaction checker with PostgreSQL-backed clinical rules, automated FDA data ingestion, and intelligent prescription OCR. Built for healthcare professionals and patients who need reliable medication safety screening with complete privacy.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.1+-green.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## ✨ Key Features

### 🔐 **Enterprise-Grade Security**
- Server-side interaction rules evaluation (never exposed to client)
- PostgreSQL connection pooling with thread-safe operations
- High-precision trigram search prevents false-positive matches
- RxNorm API proxy prevents direct client exposure

### 🧬 **Clinical Intelligence**
- **PostgreSQL-backed rules engine** with curated interaction patterns
- **openFDA SPL data ingestion** with automated ETL pipeline
- **Multi-provider LLM router** (Groq, Cerebras, Gemini, OpenRouter, HuggingFace)
- **Trigram similarity matching** (threshold 0.85) eliminates dangerous substring matches
- **Levenshtein fuzzy matching** for Indian brand name normalization
- **RxNorm integration** for standardized drug nomenclature

### 📸 **Smart Prescription Processing**
- Client-side OCR with **Tesseract.js**
- Automatic image preprocessing (grayscale, thresholding, scaling)
- Indian prescription shorthand extraction (OD, BD, TDS, etc.)
- Multi-line prescription text grouping for broken OCR output

### 💰 **Cost Savings Intelligence**
- 34 common Indian brand-to-generic mappings
- PMBJP (Jan Aushadhi) generic alternatives highlighted
- Approximate MRP pricing with regional disclaimers
- Automatic prescription matching and savings calculation

### 🎯 **User Experience**
- Medical disclaimer modal with localStorage persistence
- Emergency escalation warnings for high-risk interactions
- WhatsApp sharing and clipboard export
- Fully responsive mobile-first design

---

## 🏗️ Architecture

### Backend (Flask REST API)
```
app.py
├── GET  /                          → Render SPA shell
├── GET  /api/rxnorm/<path>         → Transparent RxNorm proxy
├── GET  /api/local-data            → Serve safe catalog data
├── POST /api/normalize-drug        → Server-side brand→generic matching
└── POST /api/check-interactions    → PostgreSQL interaction query
```

### ETL Pipeline (openFDA Ingestion)
```
etl.py
├── SEED       → Bootstrap from hardcoded INTERACTION_RULES
├── CHECKPOINT → Resume from last successful batch
├── FETCH      → Download FDA drug labels (openFDA API)
├── PARSE      → Extract drug names and interaction text
├── LLM        → Structure free-text with multi-provider router
├── LOAD       → Upsert drugs and interactions to PostgreSQL
└── COMMIT     → Atomic checkpoint update
```

### LLM Router (Multi-Provider Failover)
```
llm_router.py
├── Groq (llama-3.3-70b-versatile)     → Primary
├── Cerebras (gpt-oss-120b)            → Fallback 1
├── Gemini (gemini-2.5-flash)          → Fallback 2
├── OpenRouter (free tier)             → Fallback 3
└── HuggingFace (Meta-Llama-3-8B)      → Fallback 4
```

### Database (PostgreSQL)
```sql
-- High-precision drug resolution
CREATE TABLE drugs (
  id BIGSERIAL PRIMARY KEY,
  generic_name CITEXT UNIQUE NOT NULL,
  brand_names JSONB DEFAULT '[]'::jsonb
);
CREATE INDEX idx_drugs_name_trgm ON drugs USING gin (generic_name gin_trgm_ops);

-- Interaction rules storage
CREATE TABLE interactions (
  drug_a_id BIGINT REFERENCES drugs(id),
  drug_b_id BIGINT REFERENCES drugs(id),
  severity TEXT CHECK (severity IN ('high', 'medium', 'low')),
  description TEXT,
  action_text TEXT,
  source TEXT,
  PRIMARY KEY (drug_a_id, drug_b_id),
  CHECK (drug_a_id < drug_b_id)
);

-- ETL checkpoint for fault-tolerance
CREATE TABLE etl_sync_state (
  id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_successful_skip INT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Frontend (Vanilla JS SPA)
- **No framework dependencies** — pure JavaScript
- **Tesseract.js** for client-side OCR
- **RxNorm proxy calls** — all API traffic routed through Flask
- **LocalStorage** for disclaimer acceptance tracking

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+**
- **PostgreSQL 12+** with `pg_trgm` and `citext` extensions
- **pip** package manager
- **At least one LLM API key** (Groq, Cerebras, Gemini, OpenRouter, or HuggingFace)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/rxcheck.git
   cd rxcheck
   ```

2. **Create virtual environment**
   ```bash
   python -m venv env
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**
   ```bash
   createdb rxcheck
   psql rxcheck -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
   psql rxcheck -c "CREATE EXTENSION IF NOT EXISTS citext;"
   ```

5. **Configure environment variables**
   ```bash
   # Create .env file
   cat > .env << EOF
   DATABASE_URL=postgresql://postgres:password@localhost:5432/rxcheck
   DB_POOL_MIN=1
   DB_POOL_MAX=10
   
   # At least one LLM API key required for ETL
   GROQ_API_KEY=your_groq_key_here
   CEREBRAS_API_KEY=your_cerebras_key_here
   GEMINI_API_KEY=your_gemini_key_here
   OPENROUTER_API_KEY=your_openrouter_key_here
   HUGGING_FACE_API_KEY=your_hf_key_here
   EOF
   ```

6. **Initialize database schema**
   ```bash
   python etl.py --seed-only
   ```

7. **Run the ETL pipeline (optional)**
   ```bash
   # Fetch 100 FDA records and populate database
   python etl.py --limit 100
   
   # The pipeline automatically resumes from checkpoint on subsequent runs
   python etl.py --limit 100  # Fetches next 100 records
   ```

8. **Start the Flask application**
   ```bash
   python app.py
   ```

9. **Open in browser**
   ```
   http://localhost:5000
   ```

---

## 📁 Project Structure

```
rxcheck/
├── app.py                 # Flask REST API with connection pooling
├── data.py                # Business data (brands, prices, interaction rules)
├── etl.py                 # openFDA ingestion pipeline with checkpointing
├── llm_router.py          # Multi-provider LLM failover router
├── schema.sql             # PostgreSQL DDL (drugs, interactions, etl_sync_state)
├── .env                   # Environment configuration (not in repo)
├── .gitignore             # Git ignore patterns
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # SPA shell with disclaimer modal
├── static/
│   ├── app.js            # Client-side logic (OCR, UI, API calls)
│   └── styles.css        # Design system with emergency warning styles
└── README.md             # This file
```

---

## 🔬 How It Works

### 1. **Drug Name Resolution**
```
User Input → Server-side Levenshtein Matching → RxNorm API Lookup → PostgreSQL Trigram Search
```

**Two-tier precision strategy:**
- **Tier 1**: Exact `CITEXT` match (zero false positives)
- **Tier 2**: Trigram similarity with threshold 0.85 (blocks "folic acid" ≠ "valproic acid")

### 2. **Interaction Detection**
```
Resolved Drugs → PostgreSQL Query → Interaction Rules → Risk Categorization
```

**Server-side evaluation:**
- All interaction rules stored in `data.py` (never sent to client)
- PostgreSQL query with canonical drug pair ordering
- Cartesian product resolution for multi-ingredient drugs

### 3. **ETL Pipeline (openFDA Ingestion)**
```
Checkpoint Read → FDA API Fetch → Text Extraction → LLM Parsing → PostgreSQL Upsert → Checkpoint Write
```

**Fault-tolerance guarantees:**
- Atomic checkpoint updates (same transaction as data writes)
- Idempotent upserts (replaying batches creates no duplicates)
- Multi-provider LLM failover (automatic quota/rate-limit handling)
- Crash recovery (resumes from last successful batch)

### 4. **OCR Processing**
```
Photo Upload → Image Preprocessing → Tesseract.js → Text Extraction → Drug Name Parsing
```

**Preprocessing pipeline:**
- Grayscale conversion with luminance formula
- Binary thresholding (threshold=140)
- 2× upscaling for small images
- Indian prescription shorthand extraction

### 5. **Results Dashboard**
- **Risk Grid**: Safe / Caution / Dangerous counters
- **Interaction Cards**: Severity badges with clinical guidance
- **Generic Alternatives**: RxNorm-normalized names with Indian pricing
- **Save Money Table**: Brand-to-generic comparison with PMBJP options

---

## 🛠️ Technology Stack

### Backend
- **Flask 3.1+** — Lightweight WSGI web framework
- **psycopg2** — PostgreSQL adapter with connection pooling
- **python-dotenv** — Environment variable management
- **requests** — HTTP library for RxNorm proxy and FDA API

### ETL & AI
- **Groq** — Primary LLM provider (llama-3.3-70b-versatile)
- **Cerebras** — Fallback LLM (gpt-oss-120b)
- **Google Gemini** — Fallback LLM (gemini-2.5-flash)
- **OpenRouter** — Free tier fallback
- **HuggingFace** — Final fallback (Meta-Llama-3-8B)

### Database
- **PostgreSQL 12+** — Relational database with advanced text search
- **pg_trgm extension** — Trigram similarity matching
- **citext extension** — Case-insensitive text type

### Frontend
- **Vanilla JavaScript** — No framework overhead
- **Tesseract.js 5.x** — Pure JavaScript OCR engine
- **Custom CSS** — Design system with CSS variables
- **Google Fonts** — DM Sans & Source Sans 3

---

## 🔌 API Reference

### `GET /api/rxnorm/<path>`
Transparent proxy to `https://rxnav.nlm.nih.gov/REST/<path>`.

**Example:**
```bash
curl http://localhost:5000/api/rxnorm/rxcui.json?name=metformin
```

### `GET /api/local-data`
Serve safe catalog data (brand hints, price catalog, savings lookup).

**Response:**
```json
{
  "brand_hints": {"glycomet": "metformin", ...},
  "price_catalog": {"metformin": {...}, ...},
  "brand_savings_lookup": [...]
}
```

### `POST /api/normalize-drug`
Server-side brand→generic normalization with Levenshtein fuzzy matching.

**Request:**
```json
{
  "name": "Glycomet 500"
}
```

**Response:**
```json
{
  "normalized": "metformin",
  "catalog": {
    "display": "Metformin",
    "alternatives": ["Metformin immediate-release", "Metformin sustained-release"],
    "range": "Rs. 18-110 per strip of 10 tablets"
  }
}
```

### `POST /api/check-interactions`
Query PostgreSQL for interactions between resolved drugs.

**Request:**
```json
{
  "resolved": [
    {
      "rawName": "Warfarin",
      "genericName": "warfarin",
      "ingredients": ["warfarin"]
    },
    {
      "rawName": "Aspirin",
      "genericName": "aspirin",
      "ingredients": ["aspirin"]
    }
  ]
}
```

**Response:**
```json
{
  "findings": [
    {
      "level": "high",
      "pair": ["Warfarin", "Aspirin"],
      "message": "Higher bleeding risk when warfarin is combined with antiplatelet drugs or NSAIDs.",
      "action": "Avoid casual co-use and check INR/bleeding plan with the prescriber.",
      "source": "Internal Clinical Rules Engine"
    }
  ]
}
```

---

## 📊 Database Schema

### `drugs` Table
```sql
CREATE TABLE drugs (
  id BIGSERIAL PRIMARY KEY,
  generic_name CITEXT UNIQUE NOT NULL,
  brand_names JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX idx_drugs_name_trgm ON drugs USING gin (generic_name gin_trgm_ops);
CREATE INDEX idx_drugs_brands ON drugs USING gin (brand_names jsonb_path_ops);
```

### `interactions` Table
```sql
CREATE TABLE interactions (
  drug_a_id BIGINT NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
  drug_b_id BIGINT NOT NULL REFERENCES drugs(id) ON DELETE CASCADE,
  severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  description TEXT NOT NULL DEFAULT '',
  action_text TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'openFDA SPL',
  PRIMARY KEY (drug_a_id, drug_b_id),
  CHECK (drug_a_id < drug_b_id)
);

CREATE INDEX idx_interactions_drug_a ON interactions (drug_a_id);
CREATE INDEX idx_interactions_drug_b ON interactions (drug_b_id);
```

### `etl_sync_state` Table
```sql
CREATE TABLE etl_sync_state (
  id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_successful_skip INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 🔄 ETL Pipeline Usage

### Basic Commands

```bash
# Seed database from hardcoded rules only
python etl.py --seed-only

# Fetch 100 FDA records (resumes from checkpoint automatically)
python etl.py --limit 100

# Dry-run (fetch + parse, no database writes)
python etl.py --dry-run --limit 10

# Reset checkpoint to 0 (use with caution!)
python etl.py --reset-checkpoint

# Manual skip override (only if checkpoint is 0)
python etl.py --skip 500 --limit 100
```

### ETL Pipeline Stages

1. **SEED** — Bootstrap from `data.py` INTERACTION_RULES
2. **CHECKPOINT** — Read `etl_sync_state.last_successful_skip`
3. **FETCH** — Download batch from openFDA API
4. **PARSE** — Extract drug names and interaction text
5. **LLM** — Structure free-text with multi-provider router
6. **LOAD** — Upsert drugs and interactions to PostgreSQL
7. **COMMIT** — Atomic checkpoint update

### Fault-Tolerance Features

- **Idempotent upserts** — Replaying batches creates no duplicates
- **Atomic checkpoints** — Checkpoint and data committed in same transaction
- **Crash recovery** — Resumes from last successful batch
- **Multi-provider failover** — Automatic LLM quota/rate-limit handling

---

## 🤖 LLM Router Configuration

The ETL pipeline uses a multi-provider LLM router for fault-tolerance. Configure API keys in `.env`:

```bash
# Primary (fastest, best for JSON extraction)
GROQ_API_KEY=your_groq_key_here

# Fallbacks (tried in order when primary fails)
CEREBRAS_API_KEY=your_cerebras_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
HUGGING_FACE_API_KEY=your_hf_key_here
```

**Provider Selection Logic:**
1. Groq (llama-3.3-70b-versatile) — Primary
2. Cerebras (gpt-oss-120b) — Fallback on quota/rate-limit
3. Gemini (gemini-2.5-flash) — Fallback on Cerebras failure
4. OpenRouter (free tier) — Fallback on Gemini failure
5. HuggingFace (Meta-Llama-3-8B) — Final fallback

**Automatic Failover Triggers:**
- 429 (rate limit exceeded)
- Quota exhausted
- Capacity/overload errors
- Transient 502/504 errors (retried once)

---

## ⚠️ Medical Disclaimer

**RxCheck is an educational screening tool, not a substitute for professional medical advice.**

This application:
- ❌ Cannot replace clinical judgment or pharmacist consultation
- ❌ May miss rare interactions, allergies, or contraindications
- ❌ Does not account for patient-specific factors (age, weight, renal function, pregnancy)
- ❌ Cannot verify local brand formulations or bioequivalence

**Always confirm medication decisions with a qualified healthcare professional.**

---

## 🎨 Design Philosophy

### Security-First
- Interaction rules never leave the server
- PostgreSQL connection pooling prevents race conditions
- High-precision matching eliminates false positives
- RxNorm proxy prevents client-side API key exposure

### Clinical Accuracy
- Trigram threshold tuned to block dangerous substring matches
- Server-side Levenshtein matching for Indian brand names
- Emergency escalation warnings for high-risk interactions
- Medical disclaimer modal with persistent acceptance

### Data Integrity
- Atomic ETL checkpoints (crash-safe)
- Idempotent upserts (replay-safe)
- Multi-provider LLM failover (quota-safe)
- Canonical drug pair ordering (duplicate-safe)

### User Privacy
- No user accounts or authentication
- No prescription data storage
- Client-side OCR processing
- LocalStorage only for disclaimer acceptance

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/clinical-rule-update`)
3. Commit your changes (`git commit -m 'Add new interaction rule for X+Y'`)
4. Push to the branch (`git push origin feature/clinical-rule-update`)
5. Open a Pull Request

### Areas for Contribution
- Additional interaction rules with clinical references
- More Indian brand-to-generic mappings
- OCR accuracy improvements for handwritten prescriptions
- Internationalization (Hindi, Tamil, Bengali)
- Database migration scripts
- Additional LLM providers in router

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **National Library of Medicine** — RxNorm and RxNav APIs
- **U.S. FDA** — openFDA drug label database
- **Tesseract.js** — Open-source OCR engine
- **PostgreSQL** — Advanced open-source database
- **Google Fonts** — DM Sans and Source Sans 3 typefaces
- **PMBJP (Jan Aushadhi)** — Generic medicine pricing data
- **Groq, Cerebras, Google, OpenRouter, HuggingFace** — LLM API providers

---

## 📧 Contact

For questions, bug reports, or feature requests:
- **GitHub Issues**: [Report a bug or request a feature](https://github.com/yourusername/rxcheck/issues)
- **Email**: your.email@example.com

---

## 🌟 Star History

If you find RxCheck useful, please consider giving it a ⭐ on GitHub!

---

**Built with ❤️ for safer medication management in India**
