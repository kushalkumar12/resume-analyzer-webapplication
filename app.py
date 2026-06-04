import streamlit as st
from streamlit_extras.add_vertical_space import add_vertical_space
import google.generativeai as genai
import PyPDF2 as pdf
from dotenv import load_dotenv
import json
import re
import logging

# 1. Setup Console Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# --- APP VERSION ---
APP_VERSION = "1.0.0"

# --- PREFERRED MODELS CONFIGURATION ---
PREFERRED_MODELS = [
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-pro"
]

# --- HELPER FUNCTIONS ---

def get_available_models(api_key):
    """Filters available models against our curated list of efficient models."""
    try:
        genai.configure(api_key=api_key)
        all_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Only keep models that are in our preferred list, maintaining priority order
        active_models = [m for m in PREFERRED_MODELS if m in all_models]
        
        if not active_models:
            # Absolute fallback if preferred models aren't available for this key
            active_models = all_models[:3] 
            
        logger.info(f"Loaded high-efficiency models: {active_models}")
        return active_models
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        return []

def get_gemini_response(input_text, api_key, model_name):
    """Generates raw text response from Gemini."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(input_text)
    return response.text

def input_pdf_text(uploaded_file):
    """Extracts text from uploaded PDF."""
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in range(len(reader.pages)):
        page_obj = reader.pages[page]
        text += str(page_obj.extract_text())
    return text

def extract_json(text):
    """Robust JSON extraction handling markdown backticks."""
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        logger.warning(f"JSON Parsing failed: {e}")
        return None

def execute_with_failover(prompt, available_models, selected_model, api_key, expect_json=False):
    """Round-robin failover logic abstracted for reuse."""
    test_list = [selected_model] + [m for m in available_models if m != selected_model]
    
    for current_model in test_list:
        logger.info(f"Attempting processing with model: {current_model}")
        try:
            raw_response = get_gemini_response(prompt, api_key, current_model)
            
            if expect_json:
                parsed_data = extract_json(raw_response)
                if parsed_data:
                    return parsed_data, current_model
            else:
                if raw_response.strip():
                    return raw_response, current_model
                    
        except Exception as e:
            logger.error(f"FAILED: {current_model} | Error: {str(e)}")
            continue
            
    return None, None

# --- HIGH-ACCURACY, LOW-TOKEN ATS PROMPT ---
ats_prompt = """
Current Date Context: June 2026.
Role: Enterprise ATS Parsing Engine.
Task: Cross-verify Resume against Job Description (JD). Eliminate hallucinations.

Strict Rules:
1. Date & Experience Verification: Calculate total experience accurately based on 'June 2026'. Ensure timeline ranges up to 2026 are treated as historical/valid, NOT future dates.
2. Extraction Match: Identify hard skills, frameworks, tools, certifications, and degree requirements.
   - MatchedSkills: Present in both Resume and JD.
   - MissingSkills: Explicitly required or preferred in JD, but completely absent from Resume.
   - ExtraSkills: Present in Resume, but completely unmentioned/unrequested in JD.

Resume: {text}
JD: {jd}

Output ONLY raw, minified JSON matching this structure:
{{"JD Match": "XX%", "MatchedSkills": ["s1"], "MissingSkills": ["s2"], "ExtraSkills": ["s3"], "Profile Summary": "Objective summary of experience duration, stack alignment, and education eligibility."}}
"""

# --- UI CONFIGURATION ---

st.set_page_config(page_title="Check ATS Score", layout="wide", page_icon="📝")

with st.sidebar:
    st.title("⚙️ ATS Settings")
    user_api_key = st.text_input("Enter Google API Key", type="password")
    
    available_models = []
    api_ready = False
    
    if user_api_key:
        available_models = get_available_models(user_api_key)
        if available_models:
            st.success("API Key Validated & Models Loaded!")
            selected_model = st.selectbox("Priority Model", available_models)
            api_ready = True
        else:
            st.error("Invalid API Key or no compatible models found.")
    else:
        st.warning("Please enter your API Key.")

    st.divider()
    add_vertical_space(3)
    st.write("Made by Kushal Kumar 🐧.")
    st.caption(f"v{APP_VERSION}")

# --- MAIN APP INTERFACE ---

st.title("Smart Application Tracking System")
st.caption(f"v{APP_VERSION}  •  Round-Robin Failover Mode: Active")

if not api_ready:
    st.info("👈 Enter a valid API Key in the sidebar to begin.")
else:
    default_jd = "Enter the Job Description for evaluation."
    
    jd = st.text_area("Job Description", height=150, placeholder=default_jd)
    
    c1, c2 = st.columns(2)
    with c1:
        input_type = st.radio("Resume Input Method:", ("Upload PDF", "Paste Text"), horizontal=True)
    
    resume_text = ""
    if input_type == "Upload PDF":
        uploaded_file = st.file_uploader("Upload Your Resume (PDF)", type="pdf")
        if uploaded_file:
            resume_text = input_pdf_text(uploaded_file)
    else:
        resume_text = st.text_area("Paste Resume Content", height=200, placeholder="Paste your current resume text here...")

    if resume_text.strip() and jd.strip():
        if st.button("Calculate Objective ATS Score"):
            
            with st.status("Processing ATS Evaluation...", expanded=True) as status:
                
                # Step 1: Indicate Text Conversion
                st.write("📄 **Step 1:** Converting PDF/input to extractable text...")
                formatted_prompt = ats_prompt.format(text=resume_text, jd=jd)
                
                # Step 2: Indicate Model Request
                st.write("🧠 **Step 2:** Sending resume and JD context to the AI model...")
                final_data, working_model = execute_with_failover(
                    prompt=formatted_prompt, 
                    available_models=available_models, 
                    selected_model=selected_model, 
                    api_key=user_api_key, 
                    expect_json=True
                )

                if final_data:
                    # Step 3: Indicate which model successfully handled the failover
                    st.write(f"✅ **Step 3:** Response received! Working model: `{working_model}`")
                    
                    # Step 4: Indicate Data Structuring
                    st.write("📊 **Step 4:** Structuring data for the report...")
                    
                    # Collapse the status box and mark as complete
                    status.update(label="Analysis Complete!", state="complete", expanded=False)
                    
                    st.success(f"Analysis successfully generated using {working_model}!")
                    st.divider()
                    
                    # --- TOP METRIC & SUMMARY ---
                    m1, m2 = st.columns([1, 2])
                    with m1:
                        match_score_str = final_data.get("JD Match", "0").replace("%", "")
                        match_score = int(match_score_str) if match_score_str.isdigit() else 0
                        st.metric("Match Score", f"{match_score}%", 
                                  delta="Low Match" if match_score < 70 else "Strong Match", 
                                  delta_color="normal" if match_score >= 70 else "inverse")
                    with m2:
                        st.subheader("ATS Profile Summary")
                        st.info(final_data.get("Profile Summary"))

                    st.divider()

                    # --- COLOR INDICATED UIUX FOR SKILLS ---
                    st.subheader("📝 Detailed Keyword Breakdown")
                    
                    # Extract lists here to use directly in the columns
                    matched = final_data.get("MatchedSkills", [])
                    missing = final_data.get("MissingSkills", [])
                    extra = final_data.get("ExtraSkills", [])
                    
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.success("**✅ Matched Keywords**\n\n" + 
                                   "\n".join([f"- {skill}" for skill in matched]) if matched else "None detected.")

                    with col2:
                        st.error("**❌ Missing Keywords**\n\n" + 
                                 "\n".join([f"- {skill}" for skill in missing]) if missing else "None detected.")
                        
                    with col3:
                        st.warning("**⚠️ Extra Keywords**\n\n" + 
                                   "\n".join([f"- {skill}" for skill in extra]) if extra else "None detected.")

                else:
                    # Update status to show failure
                    status.update(label="Processing Failed", state="error", expanded=True)
                    st.error("Fatal Error: All models failed to parse the ATS evaluation.")
    else:
        st.warning("Please provide both the Job Description and your Resume.")