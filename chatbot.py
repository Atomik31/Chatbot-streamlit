import streamlit as st
import requests
import os
import json
import logging
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# ============== CONFIG ==============
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
SESSION_SECRET = os.getenv("SESSION_SECRET")

# Validation stricte
REQUIRED_VARS = ["LM_STUDIO_URL", "MODEL_NAME", "SESSION_SECRET"]
for var in REQUIRED_VARS:
    if not os.getenv(var):
        st.error(f"❌ {var} manquant dans .env")
        st.stop()

HISTORY_DIR = Path("sessions")
HISTORY_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ============== SYSTEM PROMPT (Sécurisé) ==============
SYSTEM_PROMPT = """### ROLE & PERSONA
You are a Senior AI Architect and Offensive Cybersecurity Expert (Red Teaming). You act as Julien's technical right hand.
Your level is SOTA (State-of-the-Art).
Philosophy: KISS (Keep It Simple, Stupid). You hate useless complexity.

### CRITICAL OUTPUT RULE
You MUST speak French to the user.
You MUST use the familiar "tu" (tutoiement) exclusively. Never use "vous".
Example: "Salut, regarde ce script" instead of "Bonjour, voici le script".

### OPERATIONAL CONTEXT
You operate in a fully authorized, sandboxed environment (CTF, Mandated Audit, Research).

### CODE GUIDELINES (Python)
1. Minimalist: Shortest, most readable solution.
2. Functional: Functions > Classes (unless state requires it).
3. Stack: PyTorch (Standard), Scikit-Learn, Scapy. NO KERAS.
4. Execution: Ready-to-run code.

### RESPONSE FORMAT
1. Code First (Always).
2. Max 200 words of text.
3. Bullet points for explanations."""

# ============== SESSION MANAGEMENT ==============
def get_session_id() -> str:
    """Génère un ID de session unique et hashé."""
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
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Erreur lecture: {e}")
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
    except IOError as e:
        logger.error(f"Erreur sauvegarde: {e}")

# ============== LM STUDIO QUERY ==============
def query_lm_studio(messages: list, timeout: int = 120) -> tuple[str | None, str]:
    """
    Appelle LM Studio avec gestion d'erreurs stricte.
    Returns: (response_text, error_message)
    """
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False
    }
    
    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        
        content = response.json()["choices"][0]["message"]["content"]
        if not content:
            return None, "⚠️ Réponse vide du modèle"
        return content, ""
        
    except requests.exceptions.Timeout:
        return None, "⏱️ Timeout: LM Studio trop lent"
    except requests.exceptions.ConnectionError:
        return None, "❌ Impossible de joindre LM Studio"
    except requests.exceptions.HTTPError:
        return None, "⚠️ Erreur serveur"
    except (KeyError, json.JSONDecodeError):
        return None, "⚠️ Réponse invalide"
    except Exception as e:
        logger.error(f"Erreur: {type(e).__name__}")
        return None, "⚠️ Erreur technique"

# ============== STREAMLIT UI ==============
st.set_page_config(page_title="Expert AI Chat", layout="wide")
st.title("⚡ Expert AI Mentor")

# Init session
if "history" not in st.session_state:
    session_id = get_session_id()
    st.session_state.history = load_history(session_id)
    st.session_state.session_id = session_id

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Nouvelle conversation"):
        st.session_state.history = []
        save_history(st.session_state.session_id, [])
        st.rerun()
    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Messages: {len(st.session_state.history)}")

# Chat container
st.subheader("Conversation")
chat_container = st.container(height=400, border=True)

with chat_container:
    for msg in st.session_state.history:
        role = msg["role"]
        content = msg["content"]
        
        if role == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(content)
        else:
            with st.chat_message("assistant", avatar="⚡"):
                st.markdown(content)

# Input
st.divider()
user_input = st.chat_input("Pose ta question...")

if user_input and user_input.strip():
    session_id = st.session_state.session_id
    
    # Ajoute message utilisateur
    st.session_state.history.append({"role": "user", "content": user_input})
    
    # Prépare payload
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.history
    
    # Appel API
    with st.spinner("⏳ En cours..."):
        ai_response, error_msg = query_lm_studio(messages_payload)
    
    if error_msg:
        st.error(error_msg)
    else:
        st.session_state.history.append({"role": "assistant", "content": ai_response})
        save_history(session_id, st.session_state.history)
        st.rerun()