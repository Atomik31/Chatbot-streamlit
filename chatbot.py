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
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

if not all([LM_STUDIO_URL, MODEL_NAME, SESSION_SECRET, AUTH_PASSWORD]):
    st.error("❌ Variables d'env manquantes")
    st.stop()

HISTORY_DIR = Path("sessions")
HISTORY_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """SYSTEM_PROMPT = 
You are a Python tutor for Data Science students.
Write SIMPLE, CLEAR, EDUCATIONAL code.
Goal: Student learns concepts, NOT production patterns.

### RULES
1. NO type hints.
2. NO complex error handling (basic try/except only if needed).
3. NO function wrappers (write scripts directly).
4. NO magic constants (explain what you do).
5. Comments EVERYWHERE (explain each line in FRENCH).
6. Use pandas/sklearn basics ONLY (no advanced tricks).
7. Code SHORT and READABLE (<30 lines per block).
8. Add print() to show what's happening.
9. Simple variable names (X, y, df, model).
10. Show output CLEARLY.

### LANGUAGE
- Code: English.
- Comments in code: FRANÇAIS.

### NO EXPLANATIONS
Return ONLY code in ```python ... ```
No text before or after code.
If explanation needed, student asks.

Write simple, clear code. FIN.
"""

def get_session_id() -> str:
    """Génère un ID de session hashé."""
    if "session_id" not in st.session_state:
        import uuid
        raw_id = str(uuid.uuid4())
        hashed = hashlib.sha256(f"{raw_id}{SESSION_SECRET}".encode()).hexdigest()[:16]
        st.session_state.session_id = hashed
    return st.session_state.session_id

def load_history(session_id: str) -> list:
    """Charge l'historique de conversation."""
    history_path = HISTORY_DIR / f"{session_id}.json"
    if history_path.exists():
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(session_id: str, history: list) -> None:
    """Sauvegarde l'historique avec limite de 50 messages."""
    if len(history) > 50:
        history = history[-50:]
    history_path = HISTORY_DIR / f"{session_id}.json"
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass

def query_lm_studio(messages: list) -> tuple[str | None, str]:
    """Appelle LM Studio avec le prompt système."""
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
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

# Vérify auth
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("### 🔐 Authentification")
    password = st.text_input("Mot de passe", type="password")
    
    if st.button("Accès"):
        if password == AUTH_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect")
else:
    # Init session
    if "history" not in st.session_state:
        session_id = get_session_id()
        st.session_state.history = load_history(session_id)
        st.session_state.session_id = session_id

    # Affiche le nom du modèle
    st.markdown("### ASSISTANT IA ")

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