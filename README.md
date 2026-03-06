# 🐧 Smart Application Tracking System (ATS)

A powerful, AI-driven tool designed to bridge the gap between job seekers and recruiters. This application evaluates resumes against specific Job Descriptions (JD) using **Google's Gemini Pro AI**, providing a match score, identifying missing keywords, and generating a professional profile summary.

---

## 🚀 Key Features

* **Dual Input Modes**: Analyze your resume by uploading a **PDF** or by simply **pasting the text** for rapid iteration.
* **Failover Logic**: Automatically cycles through available Gemini models if the primary model fails or hits a rate limit.
* **ATS Optimization**: Uses specialized prompts to simulate high-end enterprise ATS algorithms.
* **Live Processing Logs**: A transparent view of the background AI reasoning and model selection process.
* **Keyword Analysis**: High-accuracy identification of technical and soft-skill gaps.

---

## 🛠️ Tech Stack

* **Frontend**: [Streamlit](https://streamlit.io/)
* **AI Engine**: [Google Generative AI (Gemini)](https://ai.google.dev/)
* **PDF Parsing**: PyPDF2
* **Environment Management**: Python-dotenv

---

## 📋 Prerequisites

Before running the application, ensure you have:
1.  A **Google AI API Key** (Get it from [Google AI Studio](https://aistudio.google.com/)).
2.  Python 3.10 or higher installed.

---

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/kushalkumar12/ats-analyser-with-gemini-ai.git](https://github.com/kushalkumar12/ats-analyser-with-gemini-ai.git)
   cd smart-ats

Made by **Kushal Kumar** 🐧<br>

## ⚙️ How to Run

1. **Step 1 - Download all imports**
```bash
    pip install -r requirements.txt
```
2. **Step 2 - Get the Gemini API key**
* Sign in to **Googe AI Studio** and get the **API key**

3. **Step 3 - Run the ats-analyser-with-gemini-ai python Project**

* Regular **ATS ANALYZER** has only option to **PDF** input
```bash
    python -m streamlit run app.py
```
* **ATS ANALYZER** with backgroud Image has only option to **PDF** (optional)
```bash
    python -m streamlit run app_b.py
```
* Advance **ATS ANALYZER** has both **PDF** and **Text** input
```bash
    python -m streamlit run app_adv.py
```