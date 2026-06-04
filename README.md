# 📝 Smart ATS Analyser — Powered by Google Gemini AI

An intelligent **Applicant Tracking System (ATS) analyser** that cross-verifies your resume against a job description using **Google's Gemini AI**. Built with a **round-robin model failover engine** to ensure reliability even when individual models hit rate limits.

---

## ✨ Features

### 🔄 Round-Robin Model Failover
Automatically tries models in priority order (`gemini-1.5-pro` → `gemini-1.5-flash` → `gemini-pro`). If the preferred model fails or hits a rate limit, the engine seamlessly falls over to the next available model — zero manual intervention required.

### 📊 Objective ATS Scoring
Uses an enterprise-grade ATS prompt that:
- Calculates experience duration accurately against the current date
- Identifies hard skills, frameworks, tools, certifications, and degree requirements
- Returns a structured **JD Match %** score

### 🟩🟥🟨 Detailed Keyword Breakdown
After analysis, results are shown in three colour-coded columns:
| Column | Meaning |
|---|---|
| ✅ Matched Keywords | Skills present in **both** your resume and the JD |
| ❌ Missing Keywords | Skills required by the JD but **absent** from your resume |
| ⚠️ Extra Keywords | Skills in your resume that are **not mentioned** in the JD |

### 📄 Dual Resume Input
- **Upload PDF** — Automatically extracts text from any PDF resume via PyPDF2
- **Paste Text** — Directly paste plain-text resume content

### 🪵 Live Step-by-Step Status Log
A real-time `st.status` panel displays each processing step:
1. PDF/text conversion
2. AI model request dispatch
3. Model that successfully responded (with failover visibility)
4. Data structuring for the report

### 🔐 API Key Validation
Validates the Google AI Studio API key on entry and dynamically loads only compatible, preferred Gemini models for that key.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io/) |
| AI Engine | [Google Generative AI — Gemini](https://ai.google.dev/) |
| PDF Parsing | [PyPDF2](https://pypdf2.readthedocs.io/) |
| Environment | [python-dotenv](https://pypi.org/project/python-dotenv/) |
| Extras | [streamlit-extras](https://github.com/arnaudmiribel/streamlit-extras) |

---

## 📋 Prerequisites

- **Python 3.10+**
- A **Google AI Studio API Key** → [Get one here](https://aistudio.google.com/)

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/kushalkumar12/ats-analyser-with-gemini-ai.git
cd ats-analyser-with-gemini-ai
```

### 2. Install Dependencies

```bash
pip install streamlit streamlit-extras google-generativeai PyPDF2 python-dotenv
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

### 3. (Optional) Set API Key via `.env`

Create a `.env` file in the root directory:

```
GOOGLE_API_KEY=your_api_key_here
```

> The app also accepts the API key directly via the sidebar UI — no `.env` file is required.

---

## ▶️ Run the Application

```bash
python -m streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## 📖 How to Use

1. **Enter your Google AI Studio API Key** in the sidebar  
   → The app validates it and loads available Gemini models automatically

2. **Select Priority Model** from the sidebar dropdown  
   → The failover engine will start with this model and cycle to others if needed

3. **Paste the Job Description** into the JD text area

4. **Choose your resume input method:**
   - Upload a **PDF** file, or
   - **Paste** plain text directly

5. Click **"Calculate Objective ATS Score"**

6. View your results:
   - 🎯 **Match Score %** with a Strong/Low Match indicator
   - 📝 **ATS Profile Summary** — objective AI-generated assessment
   - ✅❌⚠️ **Keyword Breakdown** — Matched, Missing, and Extra skills

---

## 📊 Output Example

```
Match Score: 78%  →  Strong Match

ATS Profile Summary:
  Candidate has 4 years of relevant Java/Spring Boot experience.
  Missing Kafka and JVM tuning expertise required by the JD.

✅ Matched:   Java, Spring Boot, Microservices, REST APIs
❌ Missing:   Apache Kafka, JVM Optimization, Memory Profiling
⚠️ Extra:     Angular, MySQL, Docker Swarm
```

---

## 🏗️ Architecture

```
app.py
├── get_available_models()      # Validates API key, filters preferred Gemini models
├── get_gemini_response()       # Sends prompt to a specific Gemini model
├── input_pdf_text()            # Extracts text from uploaded PDF via PyPDF2
├── extract_json()              # Robust JSON parser (handles markdown code fences)
├── execute_with_failover()     # Round-robin failover across available models
│
├── ats_prompt                  # Enterprise ATS evaluation prompt (low-token, high-accuracy)
│
└── Streamlit UI
    ├── Sidebar: API key input, model selector
    ├── Main: JD input, resume input (PDF/text)
    ├── st.status: Live 4-step processing log
    └── Results: Match score metric, profile summary, 3-column keyword breakdown
```

---

## 🌐 Preferred Model Priority

The app automatically filters and prioritises models in this order:

```python
PREFERRED_MODELS = [
    "gemini-1.5-pro",    # Highest accuracy
    "gemini-1.5-flash",  # Fast & efficient
    "gemini-pro"         # Fallback
]
```

If none of the preferred models are available for your API key, it falls back to the first 3 available models.

---

## 💡 Why Use This Tool?

Most companies use ATS software to filter resumes **before** they reach a human recruiter. This tool helps you:

- 🎯 Know your exact match percentage before applying
- 🔑 Identify the exact keywords you're missing
- 📋 Understand how an ATS reads your resume
- ✏️ Optimise your resume for higher shortlisting chances

---

## ⭐ Support

If you found this project helpful, please give it a ⭐ on GitHub!

---

*Made by Kushal Kumar 🐧*
