import streamlit as st
from streamlit_extras.add_vertical_space import add_vertical_space
import google.generativeai as genai
import os
import PyPDF2 as pdf
from dotenv import load_dotenv
import json
import re
import logging

# 1. Setup Console Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# --- HELPER FUNCTIONS ---

def get_available_models(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        logger.info(f"Detected {len(models)} models available for this API key.")
        return models
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        return []

def get_gemini_response(input_text, api_key, model_name):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(input_text)
    return response.text

def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in range(len(reader.pages)):
        page_obj = reader.pages[page]
        text += str(page_obj.extract_text())
    return text

def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception as e:
        logger.warning(f"JSON Parsing failed: {e}")
        return None

# --- UI CONFIGURATION ---

input_prompt = """
Hey Act Like a skilled or very experienced ATS (Application Tracking System)
with a deep understanding of tech field, software engineering, data science, data analyst
and big data engineer. Your task is to evaluate the resume based on the given job description.

Assign the percentage Matching based on JD and identify missing keywords with high accuracy.

resume: {text}
description: {jd}

I want the response in a strictly valid JSON format with the following structure:
{{"JD Match": "percentage_value", "MissingKeywords": ["keyword1", "keyword2"], "Profile Summary": "summary_text"}}
"""

st.set_page_config(page_title="Check ATS Score 🐧", layout="wide")

with st.sidebar:
    st.title("Settings")
    user_api_key = st.text_input("Enter Google API Key", type="password")
    
    available_models = []
    api_ready = False
    
    if user_api_key:
        available_models = get_available_models(user_api_key)
        if available_models:
            st.success("API Key Validated!")
            selected_model = st.selectbox("Start with Model", available_models)
            api_ready = True
        else:
            st.error("Invalid API Key.")
    else:
        st.warning("Please enter your API Key.")

    st.divider()
    add_vertical_space(5)
    st.write("Made by Kushal Kumar 🐧.")

# --- MAIN APP INTERFACE ---

st.title("Smart Application Tracking System")
st.text("Failover Mode: Active")

if not api_ready:
    st.info("👈 Enter a valid API Key in the sidebar to begin.")
else:
    jd = st.text_area("Paste the Job Description", height=200, placeholder="Enter the job requirements here...")
    
    # NEW: Toggle for Resume Input Method
    input_type = st.radio("Resume Input Method:", ("Upload PDF", "Paste Resume Text"), horizontal=True)
    
    resume_text = ""
    
    if input_type == "Upload PDF":
        uploaded_file = st.file_uploader("Upload Your Resume (PDF)", type="pdf")
        if uploaded_file:
            resume_text = input_pdf_text(uploaded_file)
    else:
        resume_text = st.text_area("Paste your Resume Content", height=300, placeholder="Paste the text from your resume here...")

    submit = st.button("Analyze Resume")

    if submit:
        # Check if both fields are filled
        if resume_text.strip() != "" and jd.strip() != "":
            # Creating a visual log container in Streamlit
            log_container = st.expander("Show Background Process Logs", expanded=True)
            
            with st.spinner("Review With Gemini AI Processing..."):
                formatted_prompt = input_prompt.format(text=resume_text, jd=jd)
                
                # Priority list: Selected first, then all others
                test_list = [selected_model] + [m for m in available_models if m != selected_model]
                
                final_data = None
                working_model = None

                for current_model in test_list:
                    # Log to Terminal
                    logger.info(f"Attempting analysis with model: {current_model}")
                    # Log to Screen
                    log_container.write(f"🔄 Attempting: `{current_model}`")
                    
                    try:
                        raw_response = get_gemini_response(formatted_prompt, user_api_key, current_model)
                        parsed_json = extract_json(raw_response)
                        
                        if parsed_json:
                            final_data = parsed_json
                            working_model = current_model
                            logger.info(f"SUCCESS: Model {current_model} returned valid data.")
                            log_container.success(f"✅ Success with `{current_model}`")
                            break 
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"FAILED: {current_model} | Error: {error_msg}")
                        log_container.error(f"❌ `{current_model}` Failed: {error_msg[:100]}...")
                        continue

                # --- DISPLAY FINAL RESULTS ---
                if final_data:
                    st.divider()
                    st.header(f"Results Summary ({working_model})")
                    
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.metric("Match Score", final_data.get("JD Match"))
                    with c2:
                        st.subheader("Missing Keywords")
                        st.write(", ".join(final_data.get("MissingKeywords", [])))

                    st.subheader("Profile Summary")
                    st.info(final_data.get("Profile Summary"))
                else:
                    st.error("Fatal Error: All models in the list failed to respond.")
        else:
            st.warning("Please provide both the Job Description and your Resume (File or Text).")