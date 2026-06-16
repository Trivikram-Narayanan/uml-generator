"""
llm/gemini.py  –  Gemini backend (Google Generative AI)

Supported models:
  gemini-2.0-flash    fastest, cheapest, great for most diagrams
  gemini-1.5-pro      strongest quality, handles complex systems

Set in .env:
  LLM_BACKEND=gemini
  GEMINI_API_KEY=your-key-here
  GEMINI_MODEL=gemini-2.0-flash      # or gemini-1.5-pro

Get your API key free at: https://aistudio.google.com/apikey
"""
from __future__ import annotations
import os, logging
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_TOKENS     = int(os.getenv("LLM_MAX_TOKENS", "1024"))
TEMPERATURE    = float(os.getenv("LLM_TEMPERATURE", "0.2"))

SUPPORTED_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


def _get_client():
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/apikey "
            "then add GEMINI_API_KEY=your-key to backend/.env"
        )
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config={
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_TOKENS,
        },
    )


def generate_with_gemini(prompt: str) -> str:
    """Call Gemini and return the raw text response."""
    model = _get_client()
    response = model.generate_content(prompt)
    return response.text


def generate_code_with_gemini(prompt: str) -> str:
    """Separate call for code generation — slightly higher token budget."""
    import google.generativeai as genai
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config={
            "temperature": float(os.getenv("LLM_CODE_TEMPERATURE", "0.15")),
            "max_output_tokens": int(os.getenv("LLM_MAX_TOKENS", "1500")),
        },
    )
    response = model.generate_content(prompt)
    return response.text
