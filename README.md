# KTU PYQ Analyzer

An AI-powered Django web application that analyzes KTU Previous Year Question Papers using Google Gemini Vision API. It extracts questions from scanned/text PDFs, clusters repeated topics using Sentence Transformers, assigns priority tiers, and generates color-coded module-wise PDF reports via WeasyPrint.

## Key Features

- **Gemini Vision API Extraction** -- Sends scanned PDF page images directly to Gemini Flash 2.0 for accurate OCR. Never uses Tesseract.
- **GPT-4o Fallback** -- If Gemini hits rate limits, automatically falls back to GPT-4o via GitHub Models API. User notices nothing.
- **API Key Rotation** -- Thread-safe rotation across multiple Gemini API keys. One key exhausted? Next key, zero downtime.
- **Smart PDF Detection** -- PyMuPDF detects text vs scanned PDFs. Text PDFs use text pipeline, scanned PDFs use image pipeline.
- **PyMuPDF Fallback Rendering** -- If pdf2image/Poppler isn't installed, PyMuPDF renders pages natively. No Poppler dependency required.
- **Fixed KTU Module Mapping** -- Q1-2 = Module 1, Q3-4 = Module 2, Q5-6 = Module 3, Q7-8 = Module 4, Q9-10 = Module 5 (repeats for Q11-20). Auto-corrects if the LLM gets it wrong.
- **Semantic Topic Clustering** -- Sentence Transformers (all-MiniLM-L6-v2) with CUDA GPU support. AgglomerativeClustering with cosine distance threshold 0.35.
- **4-Tier Priority System**:
  - Tier 1 (Top Priority): 5+ appearances -- dark red
  - Tier 2 (High Priority): 3-4 appearances -- orange
  - Tier 3 (Medium Priority): 2 appearances -- yellow
  - Tier 4 (Low Priority): 1 appearance -- gray
- **WeasyPrint PDF Reports** -- Color-coded tier headings, question listings by year, study priority order.
- **Manual Correction Interface** -- Edit extracted question text, fix OCR mistakes, clear review flags.
- **Processing Log** -- Full pipeline details: PDF type, pipeline used, corrections made, warnings.
- **Confidence Indicators** -- Green (OK), Yellow (manually corrected), Red (needs review).
- **Interactive Analytics Dashboard** -- Chart.js bar/doughnut charts, module drill-down, cluster visualization.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Django 4.2, SQLite |
| PDF Reading | Google Gemini Flash 2.0 (primary), GPT-4o via GitHub Models (fallback) |
| PDF Detection | PyMuPDF (text vs image detection + fallback renderer) |
| Image Conversion | pdf2image + Pillow (300 DPI, optional) or PyMuPDF native rendering |
| Clustering | Sentence Transformers + scikit-learn (CUDA GPU supported) |
| PDF Reports | WeasyPrint |
| Frontend | Bootstrap 5.3, Chart.js, Bootstrap Icons |
| Environment | python-dotenv |
| Background Tasks | Python threading (daemon threads) |

## Quick Start

### Prerequisites

- Python 3.10+
- Poppler (optional -- for 300 DPI rendering via pdf2image; PyMuPDF fallback works without it)
- GTK3 runtime (required by WeasyPrint on Windows)
- NVIDIA GPU + CUDA (optional, for faster clustering)

### Installation

```bash
git clone https://github.com/vineeey/pyq-analyzer.git
cd pyq-analyzer
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

```env
# Required: At least one Gemini API key
GEMINI_API_KEYS=your-key-1,your-key-2
GEMINI_MODEL=gemini-2.0-flash

# Recommended: GitHub Models token for GPT-4o fallback
GITHUB_MODELS_TOKEN=your-github-pat-token
GITHUB_MODELS_MODEL=gpt-4o

# Optional
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Get Gemini keys from: https://aistudio.google.com/app/apikey
Get GitHub token from: https://github.com/settings/tokens (enable Models API access)

### Run

```bash
python manage.py migrate
python manage.py runserver
```

Visit `http://localhost:8000`

## Usage

### 1. Register & Login
Create an account at `/users/register/`

### 2. Upload Papers
- Go to **Papers** > **Upload**
- Enter subject name and code
- Select one or more PDF files (text or scanned)
- Papers are processed automatically in the background

### 3. How Processing Works
1. PyMuPDF checks if PDF has extractable text (>300 chars, no garbled patterns)
2. **Text PDF**: Extracted text sent to Gemini text pipeline
3. **Scanned PDF**: Pages converted to images via pdf2image (300 DPI) or PyMuPDF fallback, sent to Gemini Vision
4. If Gemini fails (rate limit/error), automatically falls back to GPT-4o
5. If model returns 404, automatically falls back from gemini-2.0-flash to gemini-1.5-flash
6. JSON response parsed with triple fallback (direct, brace extraction, regex)
7. Module assignments validated and auto-corrected using fixed KTU rules
8. Questions with short text (<10 chars) flagged for manual review

### 4. View & Correct Questions
- **Question List**: See all extracted questions with confidence colors
- **Manual Correction**: Edit question text, fix OCR errors, adjust marks
- **Processing Log**: View pipeline details, warnings, corrections for each paper

### 5. Run Topic Analysis
- Go to **Analytics** > click **Analyze Topics**
- Clustering groups similar questions across years
- Each cluster gets a priority tier based on frequency

### 6. Download Reports
- Go to **Reports** for a subject
- Download individual module PDFs or all modules as ZIP
- Reports include: tier-coded sections, question listings, study priority order

## Project Structure

```
pyq-analyzer/
├── apps/
│   ├── core/              # Home, dashboard views
│   ├── users/             # Authentication
│   ├── subjects/          # Subject & Module models
│   ├── papers/            # PDF upload, background processing
│   ├── questions/         # Question model, manual correction
│   ├── analysis/          # Gemini pipeline, extraction, validation
│   │   ├── gemini_pipeline.py   # Core: API calls, key rotation, parsing
│   │   ├── pipeline.py          # Orchestrator: process paper -> DB
│   │   └── tasks.py             # Background thread spawning
│   ├── analytics/         # Clustering, priority tiers
│   │   ├── clustering.py        # SentenceTransformer + AgglomerativeClustering
│   │   └── models.py            # TopicCluster model
│   └── reports/           # PDF generation
│       └── ktu_report_generator.py  # WeasyPrint report builder
├── templates/             # Bootstrap 5 HTML templates
├── static/                # CSS, JS
├── config/                # Django settings, URLs
├── media/                 # Uploaded papers, generated reports
├── db/                    # SQLite database
├── test_pipeline.py       # Dependency & pipeline test script
└── requirements.txt
```

## Architecture

```
PDF Upload
    |
    v
PyMuPDF: text or image?
    |
    +--[text]--> Extract text --> Gemini Text API
    |                                  |
    +--[image]--> pdf2image 300dpi --> Gemini Vision API
    |              (if unavailable)        |
    +--[image]--> PyMuPDF fallback --------+
                                           |
                    (if Gemini fails) -----+--> GPT-4o fallback
                                           |
                                           v
                              Triple JSON Parse
                                           |
                                           v
                           Validate & Correct Modules
                                           |
                                           v
                           Save Questions to DB
                                           |
                                           v
                     SentenceTransformer Embeddings (GPU)
                                           |
                                           v
                     AgglomerativeClustering (threshold=0.35)
                                           |
                                           v
                         Assign Priority Tiers (1-4)
                                           |
                                           v
                      WeasyPrint PDF Reports (color-coded)
```

## API Key Management

The system supports multiple Gemini API keys with automatic rotation:

- Keys are configured as a comma-separated list in `GEMINI_API_KEYS`
- When a key hits its daily quota (429 error), the system automatically rotates to the next key
- Rotation is thread-safe (uses `threading.Lock`)
- If all Gemini keys are exhausted, falls back to GPT-4o via GitHub Models
- The processing log records which pipeline was used for each paper

## KTU Question Number to Module Mapping

| Questions | Module |
|-----------|--------|
| Q1, Q2, Q11, Q12 | Module 1 |
| Q3, Q4, Q13, Q14 | Module 2 |
| Q5, Q6, Q15, Q16 | Module 3 |
| Q7, Q8, Q17, Q18 | Module 4 |
| Q9, Q10, Q19, Q20 | Module 5 |

This mapping is fixed and enforced server-side even if the LLM assigns a different module.

## Health Check

Visit `/health/` for a JSON status report of all dependencies:

```bash
curl http://localhost:8000/health/
```

Returns:
```json
{
  "healthy": true,
  "checks": {
    "pymupdf": {"status": true, "version": "1.24.x"},
    "pdf2image": {"status": true},
    "poppler": {"status": true, "path": "..."},
    "gemini_api_key": {"status": true, "key_count": 2, "model": "gemini-2.0-flash"},
    "google_genai": {"status": true},
    "database": {"status": true, "engine": "django.db.backends.sqlite3"},
    "media_uploads": {"status": true},
    "media_reports": {"status": true},
    "sentence_transformers": {"status": true},
    "weasyprint": {"status": true},
    "torch": {"status": true, "cuda": false}
  }
}
```

The `healthy` field is `true` only when all critical checks pass (pymupdf, gemini_api_key, google_genai, database, media_uploads).

## Testing the Pipeline

Run the test script to verify all dependencies:

```bash
python test_pipeline.py
```

This tests PyMuPDF rendering, Gemini API connectivity, ML dependencies, database access, and media directory permissions.

## License

MIT

## Acknowledgments

Built for KTU (APJ Abdul Kalam Technological University) exam preparation.
Adaptable to other universities by modifying the question-to-module mapping.
