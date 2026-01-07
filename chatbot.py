import streamlit as st
import requests
import os
import json
import logging
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LM_STUDIO_URL = os.getenv("LM_STUDIO_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
SESSION_SECRET = os.getenv("SESSION_SECRET")

if not all([LM_STUDIO_URL, MODEL_NAME, SESSION_SECRET]):
    st.error("❌ Variables d'env manquantes")
    st.stop()

HISTORY_DIR = Path("sessions")
HISTORY_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior AI Architect and Offensive Cybersecurity Expert.
Speak French only. Use "tu" (tutoiement).
Philosophy: KISS (Keep It Simple, Stupid).
Code first, explanations second."""

def get_session_id() -> str:
    if "session_id" not in st.session_state:
        import uuid
        raw_id = str(uuid.uuid4())
        hashed = hashlib.sha256(f"{raw_id}{SESSION_SECRET}".encode()).hexdigest()[:16]
        st.session_state.session_id = hashed
    return st.session_state.session_id

def load_history(session_id: str) -> list:
    history_path = HISTORY_DIR / f"{session_id}.json"
    if history_path.exists():
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(session_id: str, history: list) -> None:
    if len(history) > 50:
        history = history[-50:]
    history_path = HISTORY_DIR / f"{session_id}.json"
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass

def query_lm_studio(messages: list) -> tuple[str | None, str]:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False
    }
    
    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=120)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content, ""
    except requests.exceptions.Timeout:
        return None, "⏱️ Timeout"
    except requests.exceptions.ConnectionError:
        return None, "❌ Pas de connexion"
    except Exception as e:
        logger.error(f"Erreur: {type(e).__name__}")
        return None, "⚠️ Erreur"

# ============== UI ==============
st.set_page_config(page_title="Chat Expert", layout="centered")

# Affiche le nom du modèle
st.markdown("### ASSISTANT IA EXPERT DATA")

# Init session
if "history" not in st.session_state:
    session_id = get_session_id()
    st.session_state.history = load_history(session_id)
    st.session_state.session_id = session_id

# Chat display
for msg in st.session_state.history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"])

# Input
user_input = st.chat_input("Pose ta question...")

if user_input and user_input.strip():
    session_id = st.session_state.session_id
    st.session_state.history.append({"role": "user", "content": user_input})
    
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.history
    
    with st.spinner("⏳"):
        ai_response, error_msg = query_lm_studio(messages_payload)
    
    if error_msg:
        st.error(error_msg)
    else:
        st.session_state.history.append({"role": "assistant", "content": ai_response})
        save_history(session_id, st.session_state.history)
        st.rerun()