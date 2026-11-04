# Smart ATS Resume Analyzer

[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.52.2-FF4B4B.svg)](https://streamlit.io/)
[![Google GenAI](https://img.shields.io/badge/Google%20GenAI-v2.29-4285F4.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/pytest-40%20passed-brightgreen.svg)]()

An enterprise-grade, privacy-conscious **Applicant Tracking System (ATS) Resume Analyzer** powered by Google Gemini and deterministic software verification.

Evaluates resume compatibility against real-world Job Descriptions with **verifiable evidence quotes**, **deterministic code scoring**, **accessibility-first visualizations**, and **actionable bullet revisions**.

---

## 🎯 Architecture & Hybrid Evaluation Pipeline

Unlike naive tools that ask an LLM to invent an arbitrary percentage score, this application implements a **hybrid verification pipeline**:

```
[Job Description] + [Resume (PDF / DOCX / Text)]
                     │
                     ▼
       ┌──────────────────────────────┐
       │   1. Local Security & Checks  │
       │   - Magic Byte & Upload Check │
       │   - Deterministic ATS Format  │
       │   - Content & Metric Analysis │
       │   - Adversarial Text Defense  │
       └──────────────┬───────────────┘
                      │
                      ▼
       ┌──────────────────────────────┐
       │   2. Privacy PII Masking     │
       │   - Masks Email, Phone, URLs  │
       │   - Preserves Dates & Metrics │
       └──────────────┬───────────────┘
                      │
                      ▼
       ┌──────────────────────────────┐
       │   3. Gemini Model Engine     │
       │   - Current Text Models Only  │
       │   - Atomic Requirement JSON   │
       │   - Verbatim Evidence Quotes  │
       │   - Automatic Model Failover  │
       └──────────────┬───────────────┘
                      │
                      ▼
       ┌──────────────────────────────┐
       │   4. Code-Level Verification │
       │   - Bidirectional Aliases    │
       │   - Verbatim Quote Match (≥85%│
       │   - Unverified Claims = 0 pts │
       └──────────────┬───────────────┘
                      │
                      ▼
       ┌──────────────────────────────┐
       │   5. Deterministic Scoring   │
       │   - Formula Weights (100 pts) │
       │   - Knockout & Injection Caps │
       │   - Prioritized Top Fixes     │
       └──────────────────────────────┘
```

---

## 📊 Deterministic ATS Scoring Formula

The score is calculated deterministically in code (`ats/scoring.py`) using transparent, normalized weights:

| Evaluation Dimension | Weight | Description | Scoring Rule |
|---|:---:|---|---|
| **Must-Have Skills** | **40 pts** | Core non-negotiable technical & functional requirements | 100% credit if demonstrated in work experience; 70% if listed in skills list only; 60% if implied with verified evidence; 0% if missing or unverified. |
| **Nice-to-Have Skills** | **10 pts** | Preferred qualifications & bonus competencies | Same verification ratio as must-have skills. |
| **Experience Tenure Fit** | **20 pts** | Relevant work tenure & title seniority | `0.6 × min(Candidate_Years / Required_Years, 1.0) + 0.4 × (Title_Alignment / 2.0)`. Candidate years computed from non-overlapping resume employment dates. |
| **Education & Credentials** | **5 pts** | Degree & academic prerequisite matching | 5 pts (Met or Not Required), 3 pts (Partial), 0 pts (Not Met). |
| **ATS Readability & Format** | **15 pts** | Parsing compatibility, fonts, layout, sections | Machine-readable text, valid character encoding, contact info, standard section headers, clean single-column structure. |
| **Content Quality & Impact** | **10 pts** | Measurable achievements & strong action verbs | Quantified metrics (≥30% of bullets), strong action verbs (≥50% of bullets), avoidance of passive phrasing and first-person pronouns. |
| **Total** | **100 pts** | Normalized overall match score | **Strong (≥80)**, **Good (65–79)**, **Partial (50–64)**, **Weak (<50)**. |

### 🛡️ Safety Caps
- **Knockout Failure**: If any mandatory prerequisite (clearance, license, non-negotiable degree, visa status) is marked unmet, the final score is capped at **60.0%**.
- **Integrity Defense**: If prompt injection or adversarial text attempting to override scoring is detected in the resume, the final score is capped at **30.0%**.

---

## 🤖 Supported Gemini Models & Live Synchronization

Source of Truth: [Google Gemini API Documentation](https://ai.google.dev/gemini-api/docs/deprecations).

Only verified, active Gemini text generation models meeting current minimum versions are allowed:
- **Minimum Versions**: Flash ≥ 3.5, Flash-Lite ≥ 3.5, Pro ≥ 3.1.
- **Allowed Models**:
  - `gemini-3.8-flash` (Default, balanced speed and accuracy)
  - `gemini-3.7-flash` (High-throughput generation)
  - `gemini-3.6-flash` (Fast structured extraction)
  - `gemini-3.5-flash` (Established baseline text generation)
  - `gemini-3.5-flash-lite` (Ultra-lightweight extraction)
  - `gemini-3.1-pro-preview` (Deep reasoning & complex evaluation)
- **Automatic Inclusion**: Future versions (e.g. 3.9, 4.0) are automatically discovered and included without code modifications.
- **Excluded**: Legacy 2.x models, deprecated `gemini-3.1-flash-lite`, image/video/audio/TTS/Live models, embedding models, and `-latest` alias models.
- **Automatic Failover**: Capped at 3 attempts, ranking GA models before Preview models.

---

## 🔒 Security & Privacy

1. **Client-Side Secrets**: API keys are accepted through masked password inputs per-session, never stored in databases, never written to disk, and never exposed in logs or frontend bundles.
2. **API Key Scrubbing**: Automated regex scrubbing redacts any `AIza...` pattern or session key from error messages and diagnostic displays.
3. **PII Masking**: Candidate emails, phone numbers, profile URLs, and government IDs are masked (`[EMAIL]`, `[PHONE]`, `[LINK]`, `[GOV_ID]`) before transmitting to Gemini. Scoring and ATS format checks run locally on raw text.
4. **Upload Hardening**:
   - Max 5 MB file size limit.
   - Header magic-byte inspection (`%PDF` for PDF, `PK\x03\x04` for DOCX).
   - PDF encrypted/password-protection rejection.
   - DOCX zip-bomb defense (entry count limit, uncompressed size limit, compression ratio cap, and `word/document.xml` validation).
5. **Rate Limiting**: In-memory session rate limiter enforces minimum intervals (8 seconds) and hourly caps (15 runs/hour).

---

## ♿ Accessibility & Visualizations

- **WCAG 2.2 Level AA Considerations**:
  - High Contrast Mode toggle.
  - Text scaling options (Normal, Large, Extra Large).
  - Screen Reader "Tables-Only" mode that replaces interactive charts with accessible semantic tables.
  - Visible keyboard focus indicators (`:focus-visible`).
  - System `prefers-reduced-motion` compliance.
- **Plotly Visualizations**:
  - Uses the **Colorblind-safe Okabe-Ito palette** (`#009E73`, `#56B4E9`, `#E69F00`, `#D55E00`, `#0072B2`).
  - Score Gauge, Evaluation Radar Fit, Points Earned vs Potential Gain, Requirement Coverage Donut, Requirement Credit Bar Chart, ATS Compliance Stacked Bars, and Tenure Bullet Chart.
  - Every chart includes plain-language alt text and a collapsible data table.

---

## 🚀 Installation & Quickstart

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Google AI Studio API Key ([Get one here](https://aistudio.google.com/))

### 1. Clone & Setup
```bash
git clone https://github.com/kushalkumar12/resume-analyzer-webapplication.git
cd resume-analyzer-webapplication
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

To install testing dependencies:
```bash
pip install -r requirements-dev.txt
```

### 3. Optional Environment Configuration
You can optionally create a `.env` file to provide your API key automatically:
```bash
echo GOOGLE_API_KEY="your-google-ai-studio-api-key" > .env
```
*(Note: You can also enter the API key directly in the application sidebar at runtime).*

### 4. Run Application
```bash
python -m streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🧪 Automated Testing

Run the full automated test suite (100% offline, mocked Gemini API):
```bash
python -m pytest -v
```

Test coverage includes:
- `tests/test_matching.py`: Bidirectional aliases (`k8s` <-> `Kubernetes`, `CI/CD`), strict language boundaries (`C` vs `C++` vs `C#`), token-overlap quote verification, standalone skills list detection.
- `tests/test_checks.py`: Deterministic format checks, scanned/short document detection, pronoun detection, action verbs, non-overlapping work experience years calculation.
- `tests/test_scoring.py`: Deterministic score reproducibility, hallucinated quote zero-credit, skills list 70% credit, knockout cap (60%), injection cap (30%).
- `tests/test_registry.py`: Model filtering, minimum version gates, ranking, failover chain.
- `tests/test_security.py`: API key format validation, sensitive key scrubbing, literal text escaping, PII masking, upload security, rate limiting.
- `tests/test_llm.py`: Error categorization (auth, quota, not found, transient), mock failover, defensive JSON normalization.
- `tests/test_apptest.py`: Streamlit `AppTest` end-to-end user workflows, error states, and rendering.

---

## 📁 Repository Structure

```
├── app.py                 # Streamlit UI, form handling, and tab views
├── ats/
│   ├── __init__.py        # Package initializer
│   ├── models.py          # Pydantic schemas for LLM and evaluation data
│   ├── prompts.py         # System instruction and untrusted data prompt builder
│   ├── llm.py             # Per-request Gemini client, retry, and failover
│   ├── registry.py        # Model filtering, version rules, and failover chain
│   ├── matching.py        # Alias resolution, term boundaries, and evidence verification
│   ├── checks.py          # Deterministic format, content, and experience tenure checks
│   ├── scoring.py         # Transparent, deterministic 100-point scoring engine
│   ├── validate.py        # Defensive JSON sanitization, clamping, and repair
│   ├── insights.py        # Prioritized top fixes with point gain estimations
│   ├── viz.py             # Colorblind-safe Plotly charts with alt-text and table data
│   ├── security.py        # Upload hardening, PII masking, escaping, and rate limiting
│   ├── extract.py         # PDF and DOCX text extraction with scanned PDF detection
│   ├── samples.py         # Sample Job Description and Resume for 1-click demos
│   └── analysis.py        # Analysis orchestration pipeline
├── tests/                 # 40 comprehensive unit, integration, and AppTest tests
├── .streamlit/
│   └── config.toml        # Hardened Streamlit configuration (XSRF, CORS, max upload)
├── .devcontainer/
│   └── devcontainer.json  # Devcontainer specification
├── requirements.txt       # Pinned production dependencies
├── requirements-dev.txt   # Pinned test dependencies
└── README.md              # Documentation and system guide
```

---

## ⚠️ Disclaimer

This application provides compatibility estimations based on industry-standard ATS parsing heuristics, skill extraction best practices, and recruiter screening criteria. **No automated software can reproduce an employer's proprietary, customized, or third-party screening algorithm.** This tool is intended for resume optimization and career guidance.
