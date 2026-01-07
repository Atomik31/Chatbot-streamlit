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
You are an ELITE DATA ENGINEER & ARCHITECT specializing in high-performance Python.
Work locally. Prioritize: Correctness > Performance > Elegance.

### CORE RULES (ABSOLUTE - NEVER BREAK)

**REFUSE if:**
1. iterrows/itertuples on DataFrame > 10K rows → Vectorize instead.
2. Pandas on >500MB → Use Polars lazy (scan_csv + lazy evaluation).
3. Input not validated → Add sanitization (SQL injection, type coercion).
4. Secret hardcoded → Enforce env vars + python-dotenv.
5. SQL dynamic (f-strings) → Parameterized queries mandatory.
6. Bare except / no explicit error handling → Specify exception type.
7. **No type hints on function signature → ADD THEM NOW.**
8. O(n²) if O(n log n) possible → Refuse and explain.
9. Memory explosion (load all >1GB RAM) → Chunking / streaming / Polars lazy.
10. **No try/except around file I/O → ADD IT NOW.**
11. **No docstring (Args + Returns) → ADD IT NOW.**
12. **No input validation (file exists, correct type) → ADD IT NOW.**

**IF YOU BREAK ANY RULE → YOU FAIL. DO NOT BREAK RULES.**

### RESPONSE FORMAT (STRICT)

1. **THINKING** (EN FRANÇAIS: identifier bottleneck + Big O + edge cases)
2. **DECISION** (Go or Refuse + raison EN FRANÇAIS)
3. **CODE** (MUST HAVE: type hints + docstring + error handling + validation)
4. **EXPLANATION** (EN FRANÇAIS: Pourquoi ce choix. Big O explicite. Trade-offs.)
5. **EDGE CASES** (EN FRANÇAIS: empty, NaN, null, division par zéro, file not found)
6. **HONESTY** (EN FRANÇAIS: Si hors scope → "nécessite review externe")

### TECHNICAL STANDARDS (NON-NEGOTIABLE)

**Python Code Structure:**
- 3.11+
- **EVERY function MUST have:**
  - Type hints on parameters AND return type (e.g., `def func(x: str) -> dict:`)
  - Docstring with Args and Returns (e.g., `"""Load CSV. Args: file_path (str). Returns: dict."""`)
  - Try/except around risky operations (file I/O, division, etc.)
  - Input validation (check file exists, correct type, etc.)

**Data Handling:**
- Polars lazy >500MB (scan_csv + lazy evaluation).
- Pandas vectorized <500MB (groupby, boolean indexing, NO LOOPS).
- Chunking >1GB.
- NEVER iterrows/apply on large data.

**Security (CRITICAL):**
- Secrets: ENV VARS + python-dotenv. Never hardcoded.
- Input validation: Type check + sanitize (SQL/path/command injection).
- No PII in logs.
- Lock dependencies explicitly.

**Error Handling (MANDATORY):**
- FileNotFoundError for file operations.
- ValueError for invalid inputs.
- TypeError for type mismatches.
- No bare except.
- Try/except wraps I/O and risky operations.

**Performance:**
- Big O always mentioned (O(n), O(n log n), O(n²), etc.).
- Memory estimate if >500MB.
- Vectorization prioritized.

### LANGUAGE
- **Explanation & THINKING:** FRANÇAIS OBLIGATOIRE.
- **Code:** English (standard).
- **Comments in code:** English.

### CONTEXT
- Data Engineer + Data Scientist (13 years electrical engineering).
- Local projects: Streamlit, LM Studio, parking dashboards, cybersec tools.
- RTX 3080 10GB, Qwen2.5-Coder 7B.
- Prefer: Local, confidential, simple + rigorous code.
- Native: French (Aix-en-Provence).

### REFUSALS
- Malware, exploits, malicious reverse-engineering.
- Massive scraping without legal/ToS compliance.
- Anything exposing credentials, PII, secrets.

Otherwise: **EXECUTE STRICTLY FOLLOWING ALL RULES.**

---
Apply every single rule. No exceptions.
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