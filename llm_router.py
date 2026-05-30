"""
llm_router.py — RxCheck Multi-Provider LLM Router
Fails over automatically when quota or rate limits hit during FDA data ingestion.
Ensures deterministic JSON extraction with temperature=0.0.
"""

import os
import time
from dotenv import load_dotenv

# Optional imports so the app doesn't crash if a library is missing
try: from groq import Groq
except ImportError: Groq = None

try: from openai import OpenAI
except ImportError: OpenAI = None

try: from google import genai
except ImportError: genai = None

try: from huggingface_hub import InferenceClient
except ImportError: InferenceClient = None

import io
try: import PIL.Image
except ImportError: PIL = None
load_dotenv()

# =========================
# API KEYS
# =========================
GROQ_KEY = os.getenv("GROQ_API_KEY")
CEREBRAS_KEY = os.getenv("CEREBRAS_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
HF_KEY = os.getenv("HUGGING_FACE_API_KEY")

# =========================
# CLIENT INITIALIZATION
# =========================
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY and Groq else None

cerebras_client = OpenAI(
    api_key=CEREBRAS_KEY,
    base_url="https://api.cerebras.ai/v1"
) if CEREBRAS_KEY and OpenAI else None

gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY and genai else None

openrouter_client = OpenAI(
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1"
) if OPENROUTER_KEY and OpenAI else None

hf_client = InferenceClient(token=HF_KEY) if HF_KEY and InferenceClient else None


# =========================
# ERROR DETECTION
# =========================
def is_quota_error(e: Exception) -> bool:
    txt = str(e).lower()
    keywords = [
        "429", "quota", "rate", "capacity", "limit",
        "exceeded", "too many", "overloaded", "busy", "400", "insufficient"
    ]
    return any(k in txt for k in keywords)


# =========================
# PROVIDER FUNCTIONS
# =========================
def groq_chat(msgs):
    if not groq_client: raise RuntimeError("Groq key missing")
    r = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=msgs,
        temperature=0.0
    )
    return r.choices[0].message.content

def cerebras_chat(msgs):
    if not cerebras_client: raise RuntimeError("Cerebras key missing")
    r = cerebras_client.chat.completions.create(
        model="gpt-oss-120b",
        messages=msgs,
        temperature=0.0
    )
    return r.choices[0].message.content

def gemini_chat(msgs):
    if not gemini_client: raise RuntimeError("Gemini key missing")
    # Convert standard msgs to a single prompt for reliable Gemini extraction
    text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in msgs])
    r = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=text,
        config={"temperature": 0.0}
    )
    return r.text

def openrouter_chat(msgs):
    if not openrouter_client: raise RuntimeError("OpenRouter key missing")
    r = openrouter_client.chat.completions.create(
        model="openrouter/free",
        messages=msgs,
        temperature=0.0,
        extra_headers={
            "HTTP-Referer": "https://github.com/rxcheck",
            "X-Title": "RxCheck Clinical ETL"
        }
    )
    return r.choices[0].message.content

def hf_chat(msgs):
    if not hf_client: raise RuntimeError("HF key missing")
    r = hf_client.chat_completion(
        model="meta-llama/Meta-Llama-3-8B-Instruct",
        messages=msgs,
        max_tokens=1024,
        temperature=0.1 # HF often doesn't accept strict 0.0 depending on the endpoint
    )
    return r.choices[0].message.content


# =========================
# CORE ROUTER
# =========================
# Ordered by speed, context window, and reasoning capability for JSON.
CLINICAL_PROVIDERS = [groq_chat, cerebras_chat, gemini_chat, openrouter_chat, hf_chat]

def extract_clinical_data(system_prompt: str, user_prompt: str) -> str:
    """
    Attempts to extract JSON using the best available models.
    Automatically fails over to the next provider if one crashes or rate-limits.
    """
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    last_error = None

    for provider in CLINICAL_PROVIDERS:
        try:
            return provider(msgs)
        except Exception as e:
            last_error = e
            # If the provider failed because the key is missing, move on silently.
            if "key missing" in str(e):
                continue
                
            print(f"[Router] {provider.__name__} failed: {e}")

            if is_quota_error(e):
                print(f"[Router] Quota/Rate Limit hit on {provider.__name__} → Switching to next provider.")
                continue

            # For transient non-quota errors (like 502/504), wait 1 sec and retry once
            time.sleep(1.0)
            try:
                return provider(msgs)
            except Exception:
                continue

    raise RuntimeError(f"CRITICAL: All LLM providers failed. Last error: {last_error}")

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Passes raw image bytes to Gemini 2.5 Flash for clinical OCR.
    """
    if not gemini_client:
        raise RuntimeError("Gemini API key is missing.")
    if not PIL:
        raise RuntimeError("Pillow is not installed. Run `pip install pillow`.")
    
    # Convert raw bytes into a PIL Image object that the Gemini SDK can read natively
    image = PIL.Image.open(io.BytesIO(image_bytes))
    
    prompt = """You are a clinical data extraction engine. 
Analyze this prescription image. Your ONLY job is to identify the prescribed medications.

CRITICAL INSTRUCTIONS:
1. IGNORE patient names, clinic addresses, contact numbers, dates, and doctor signatures.
2. IGNORE instructions like "take after meals" or "keep out of reach of children."
3. Extract ONLY the drug names (brand or generic) and their dosages/forms.
4. Output them as a clean, vertical list, one drug per line.

EXAMPLE OUTPUT FORMAT:
Ecosprin 75mg
Combiflam
Metformin 500mg SR

Do NOT output markdown formatting (no ```). Do not number the list. Do not include conversational filler. Just the raw list."""

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image],
        config={"temperature": 0.0}
    )
    return response.text