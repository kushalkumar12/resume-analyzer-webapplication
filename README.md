Here is your **updated `README.md` code** with the **content from the attached manual added into it** as a **Usage Guide section**. I kept your GitHub style formatting clean so it looks professional.

You can **replace your README.md with this**.

````md
# ats-analyser-with-gemini-ai

A basic application that evaluates the ATS match score between your resume (CV) and a job description before you apply for a job.

Evaluates the compatibility between a candidate's resume and a job description by generating an **ATS match score**.

This application uses the **Google AI Studio API key** to access the **Gemini model**, analyze the resume and job description, and generate results along with a high-level candidate summary.

---

# 🐧 Smart Application Tracking System (ATS)

A powerful, AI-driven tool designed to bridge the gap between job seekers and recruiters. This application evaluates resumes against specific **Job Descriptions (JD)** using **Google's Gemini AI**, providing:

- ATS Match Score
- Missing Keywords
- Professional Candidate Summary

---

# 🚀 Key Features

### Dual Input Modes
Analyze your resume by:
- Uploading a **PDF Resume**
- **Pasting Resume Text** directly

### Failover Logic
Automatically cycles through available **Gemini models** if the primary model fails or hits a rate limit.

### ATS Optimization
Uses specialized prompts to simulate **enterprise ATS algorithms** used by recruiters.

### Live Processing Logs
Displays real-time background processing logs for transparency.

### Keyword Analysis
Identifies **missing technical skills and soft skills** from the job description.

---

# 🛠️ Tech Stack

Frontend  
- **Streamlit**

AI Engine  
- **Google Generative AI (Gemini)**

PDF Parsing  
- **PyPDF2**

Environment Management  
- **Python-dotenv**

---

# 📋 Prerequisites

Before running the application, ensure you have:

1. A **Google AI Studio API Key**
   
   Get it from:  
   https://aistudio.google.com/

2. **Python 3.10 or higher**

---

# ⚙️ Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/kushalkumar12/ats-analyser-with-gemini-ai.git
cd ats-analyser-with-gemini-ai
````

---

### 2️⃣ Install Required Dependencies

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Get Google Gemini API Key

1. Open **Google AI Studio**
2. Generate your **API Key**
3. Copy the key

---

# ▶️ Run the Application

```bash
python -m streamlit run app.py
```

---

# 🌐 Live Application

You can also try the hosted version:

[https://ats-analyser-for-bug.streamlit.app/](https://ats-analyser-for-bug.streamlit.app/)

---

# 📖 How to Use the ATS Analyzer

Follow these steps to evaluate your resume against a job description.

1️⃣ Open any web browser.

2️⃣ Go to the application:

```
https://ats-analyser-for-bug.streamlit.app/
```

3️⃣ Enter your **Google AI Studio API Key** in the API key field.

4️⃣ After entering the key, click anywhere outside the field to validate it.

5️⃣ Paste the **Job Description (JD)** from the job posting.

6️⃣ Choose one input method for your resume:

* **Upload PDF** – Upload your resume file
* **Paste Resume Text** – Paste resume content directly

7️⃣ Click **Analyze Resume**.

8️⃣ The system will process the request using the **Gemini model**.

9️⃣ After processing, the application will display:

* **ATS Score (Percentage Match)**
* **Missing Keywords**
* **Candidate Profile Summary**

This helps you optimize your resume before applying for the job. 

---

# 📊 Output Example

The system generates:

* ATS Match Score (e.g., **77% match**)
* Missing Keywords from the job description
* Professional Candidate Summary

These insights help you improve your resume for better ATS compatibility.

---

# 💡 Why This Tool?

Many companies use **Applicant Tracking Systems (ATS)** to filter resumes before they reach recruiters.

This tool helps job seekers:

* Identify missing skills
* Improve resume keywords
* Increase chances of passing ATS screening

---

# 👨‍💻 Author

**Kushal Kumar** 🐧

GitHub:
[https://github.com/kushalkumar12](https://github.com/kushalkumar12)

---

# ⭐ Support

If you found this project helpful, please give it a ⭐ on GitHub!

```

---

✅ This version now includes:
- Your **original README**
- **Manual instructions from the PDF** integrated as *How to Use*
- **Cleaner GitHub structure**
- **Better formatting for recruiters and developers**

---

💡 If you want, I can also give you a **🔥 “Senior-level GitHub README version”** that includes:

- Demo GIF  
- Architecture diagram  
- Project folder structure  
- Screenshots  
- Badges (Python, Gemini AI, Streamlit)

That version **looks much more impressive to recruiters.**
```
