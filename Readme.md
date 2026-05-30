# 💊 RxCheck — Clinical Drug Interaction Safety Dashboard

**RxCheck** is a production-grade drug interaction checker with PostgreSQL-backed clinical rules, server-side security, and intelligent prescription OCR. Built for healthcare professionals and patients who need reliable medication safety screening with complete privacy.

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
- **PostgreSQL-backed rules engine** with 17 curated interaction patterns
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

### Database (PostgreSQL)
```sql
-- High-precision drug resolution
CREATE TABLE drugs (
  id SERIAL PRIMARY KEY,
  generic_name CITEXT UNIQUE NOT NULL  -- Case-insensitive exact match
);
CREATE INDEX idx_drugs_trgm ON drugs USING gin (generic_name gin_trgm_ops);

-- Interaction rules storage
CREATE TABLE interactions (
  id SERIAL PRIMARY KEY,
  drug_a_id INT REFERENCES drugs(id),
  drug_b_id INT REFERENCES drugs(id),
  severity TEXT CHECK (severity IN ('high', 'medium', 'low')),
  description TEXT,
  action_text TEXT,
  source TEXT
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
- **PostgreSQL 12+** with `pg_trgm` extension
- **pip** package manager

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
   pip install flask psycopg2-binary python-dotenv requests
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
   echo "DATABASE_URL=postgresql://postgres:password@localhost:5432/rxcheck" > .env
   echo "DB_POOL_MIN=1" >> .env
   echo "DB_POOL_MAX=10" >> .env
   ```

6. **Seed the database**
   ```bash
   python etl.py --seed-only
   ```

7. **Run the application**
   ```bash
   python app.py
   ```

8. **Open in browser**
   ```
   http://localhost:5000
   ```

---

## 📁 Project Structure

```
rxcheck/
├── app.py                 # Flask REST API with connection pooling
├── data.py                # Business data (brands, prices, interaction rules)
├── etl.py                 # Database seeding script
├── .env                   # Environment configuration (not in repo)
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

### 3. **OCR Processing**
```
Photo Upload → Image Preprocessing → Tesseract.js → Text Extraction → Drug Name Parsing
```

**Preprocessing pipeline:**
- Grayscale conversion with luminance formula
- Binary thresholding (threshold=140)
- 2× upscaling for small images
- Indian prescription shorthand extraction

### 4. **Results Dashboard**
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
- **requests** — HTTP library for RxNorm proxy

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
  id SERIAL PRIMARY KEY,
  generic_name CITEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_drugs_trgm ON drugs USING gin (generic_name gin_trgm_ops);
```

### `interactions` Table
```sql
CREATE TABLE interactions (
  id SERIAL PRIMARY KEY,
  drug_a_id INT NOT NULL REFERENCES drugs(id),
  drug_b_id INT NOT NULL REFERENCES drugs(id),
  severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  description TEXT NOT NULL,
  action_text TEXT NOT NULL,
  source TEXT DEFAULT 'Internal Clinical Rules Engine',
  created_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT unique_drug_pair UNIQUE (drug_a_id, drug_b_id),
  CONSTRAINT ordered_pair CHECK (drug_a_id < drug_b_id)
);

CREATE INDEX idx_interactions_pair ON interactions (drug_a_id, drug_b_id);
```

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

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **National Library of Medicine** — RxNorm and RxNav APIs
- **Tesseract.js** — Open-source OCR engine
- **PostgreSQL** — Advanced open-source database
- **Google Fonts** — DM Sans and Source Sans 3 typefaces
- **PMBJP (Jan Aushadhi)** — Generic medicine pricing data

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
