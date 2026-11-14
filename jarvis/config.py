"""Settings, all overridable with environment variables (see .env.example)."""
import json
import os

# Tried in order. If one fails (rate limit, server error, timeout), the next one answers.
DEFAULT_PROVIDERS = [
    {"name": "groq-gpt-oss-120b", "base_url": "https://api.groq.com/openai/v1",
     "model": "openai/gpt-oss-120b", "key_env": "GROQ_API_KEY", "extra": {"reasoning_effort": "low"}},
    {"name": "groq-gpt-oss-20b", "base_url": "https://api.groq.com/openai/v1",
     "model": "openai/gpt-oss-20b", "key_env": "GROQ_API_KEY", "extra": {"reasoning_effort": "low"}},
]


def providers():
    """JARVIS_PROVIDERS can hold a JSON list in the same shape as DEFAULT_PROVIDERS
    (any OpenAI-compatible chat API works: OpenAI, Groq, a local server, ...)."""
    raw = os.environ.get("JARVIS_PROVIDERS")
    return json.loads(raw) if raw else DEFAULT_PROVIDERS


WHISPER_MODEL = os.environ.get("JARVIS_WHISPER_MODEL", "base.en")
VOICE = os.environ.get("JARVIS_VOICE", "en-GB-RyanNeural")
TASKS_FILE = os.environ.get("JARVIS_TASKS_FILE", os.path.join(os.path.dirname(__file__), "..", "examples", "tasks.json"))
DRY_RUN = os.environ.get("JARVIS_DRY_RUN", "") == "1"   # tools describe what they would do instead of doing it

SYSTEM_PROMPT = """You are Jarvis, a concise voice assistant running on the user's PC.
Answers are spoken out loud, so keep them short and natural: one to three sentences, no lists, no markdown.
Use a tool only when the user clearly asks for that action. Slang is not a command:
"lock in" means focus, not lock the computer."""
