# 💊 RxCheck — Clinical Drug Interaction Safety Dashboard

**RxCheck** is a clinical-grade, browser-based drug interaction checker that helps patients and healthcare professionals verify medication safety, identify generic alternatives, and review risk signals instantly—all with complete privacy.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-green.svg)

---

## ✨ Features

### 🔍 **Drug Interaction Analysis**
- Real-time interaction checking using **RxNorm API** from the National Library of Medicine
- Local safety rules for offline fallback
- Risk categorization: **Safe**, **Caution**, and **Dangerous**
- Clinical-grade severity assessment with actionable recommendations

### 📸 **Prescription Photo OCR**
- Upload prescription photos directly from your device
- Automatic text extraction using **Tesseract.js**
- Image preprocessing for enhanced OCR accuracy
- Manual text correction support

### 💰 **Generic Medicine Savings**
- Compare 30+ common Indian brand medicines with generic equivalents
- Approximate MRP pricing for cost comparison
- Automatic highlighting of medicines in your prescription
- Potential savings calculator

### 🔒 **Privacy-First Design**
- All processing happens in your browser
- No prescription data sent to external servers (except RxNorm API for drug normalization)
- No user accounts or data storage
- Complete anonymity

### 📤 **Easy Sharing**
- Generate doctor visit summaries
- Copy to clipboard or share via WhatsApp
- Export interaction findings for medical consultations

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/indiser/Rxcheck.git
   cd rxcheck
   ```

2. **Install dependencies**
   ```bash
   pip install flask
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open in browser**
   ```
   http://localhost:5000
   ```

---

## 📁 Project Structure

```
rxcheck/
├── app.py                 # Flask application server
├── templates/
│   └── index.html        # Main application interface
├── static/
│   ├── app.js            # Core application logic
│   └── styles.css        # UI styling and design system
└── README.md             # Project documentation
```

---

## 🎯 How It Works

### 1. **Input Methods**
- **Manual Entry**: Type drug names separated by commas
- **Prescription Text**: Paste OCR-extracted text from prescriptions
- **Photo Upload**: Upload prescription images for automatic extraction

### 2. **Drug Normalization**
- Queries **RxNorm API** to standardize drug names
- Maps Indian brand names to generic equivalents
- Identifies active ingredients

### 3. **Interaction Detection**
- Checks all drug pairs for known interactions
- Uses both online (RxNav) and local safety rules
- Categorizes findings by severity level

### 4. **Results Dashboard**
- Visual risk summary with color-coded cards
- Detailed interaction findings with clinical guidance
- Generic alternatives with Indian price estimates
- Brand-to-generic savings comparison table

---

## 🛠️ Technology Stack

### Backend
- **Flask** — Lightweight Python web framework
- **Python 3.8+** — Core application logic

### Frontend
- **Vanilla JavaScript** — No framework dependencies
- **Tesseract.js** — Client-side OCR processing
- **RxNorm REST API** — Drug normalization and interaction data

### Design
- **Custom CSS** — Modern, accessible design system
- **DM Sans & Source Sans 3** — Professional typography
- **Responsive layout** — Mobile-first approach

---

## 🔌 API Integration

### RxNorm REST API
RxCheck uses the free **RxNorm API** provided by the U.S. National Library of Medicine:

- **Drug Normalization**: `/rxcui.json`
- **Generic Lookup**: `/rxcui/{id}/generic.json`
- **Ingredient Extraction**: `/rxcui/{id}/related.json`
- **Interaction Check**: `/interaction/list.json`

**No API key required** — Public access with rate limiting.

---

## 📊 Data Sources

### Interaction Rules
- **RxNav Interaction API** — Primary source for drug-drug interactions
- **Local Safety Rules** — Curated list of 13 high-risk interaction patterns
- **Clinical Guidelines** — Based on established pharmacology references

### Price Catalog
- **30 Common Indian Brands** — Approximate MRP data
- **Generic Alternatives** — Estimated price ranges
- **Disclaimer**: Prices are approximate and vary by region, strength, and manufacturer

---

## ⚠️ Medical Disclaimer

**RxCheck is for screening and educational purposes only.**

This tool:
- ❌ Cannot replace professional medical advice
- ❌ May miss interactions, allergies, or contraindications
- ❌ Does not account for patient-specific factors (age, weight, renal function)
- ❌ Cannot verify local brand formulations

**Always confirm medication decisions with a qualified clinician or pharmacist.**

---

## 🎨 Design Philosophy

### Accessibility
- ARIA labels and semantic HTML
- Keyboard navigation support
- High contrast color scheme
- Screen reader compatible

### User Experience
- Progressive disclosure of complexity
- Clear visual hierarchy
- Instant feedback on actions
- Mobile-responsive design

### Performance
- Client-side processing for speed
- Debounced API calls
- Optimized image preprocessing
- Minimal dependencies

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Areas for Contribution
- Additional drug interaction rules
- More Indian brand-to-generic mappings
- Improved OCR accuracy
- Internationalization (i18n)
- Additional API integrations

---

## 📝 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **National Library of Medicine** — RxNorm and RxNav APIs
- **Tesseract.js** — Open-source OCR engine
- **Google Fonts** — DM Sans and Source Sans 3 typefaces

---

## 📧 Contact

For questions, suggestions, or feedback:
- **GitHub Issues**: [Report a bug or request a feature](https://github.com/indiser/Rxcheck/issues)
- **Email**: indiser01@gmail.com

---

## 🌟 Star History

If you find RxCheck useful, please consider giving it a ⭐ on GitHub!

---

**Built with ❤️ for safer medication management**
