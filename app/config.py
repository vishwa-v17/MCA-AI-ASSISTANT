import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mca_assistant.db')
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'smartgpt_config.json')
    PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'system-prompt.txt')

    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
    USER_KEY_ENCRYPTION_SECRET = os.environ.get("USER_KEY_ENCRYPTION_SECRET", "").strip()
    DEFAULT_OPENROUTER_MODEL = os.environ.get("DEFAULT_OPENROUTER_MODEL", "openrouter/free").strip()
    OPENROUTER_MODEL_CACHE_TTL = int(os.environ.get("OPENROUTER_MODEL_CACHE_TTL", "900"))

    # Per-user limits for the shared server key. Kept configurable so a
    # college/demo deployment can tune them without changing source code.
    AI_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AI_RATE_LIMIT_PER_MINUTE", "10"))
    AI_RATE_LIMIT_PER_HOUR = int(os.environ.get("AI_RATE_LIMIT_PER_HOUR", "100"))
    MAX_AI_MESSAGE_LENGTH = int(os.environ.get("MAX_AI_MESSAGE_LENGTH", "12000"))

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'webp'}

    @classmethod
    def get_system_prompt(cls):
        if os.path.exists(cls.PROMPT_FILE):
            with open(cls.PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return content if content else "You are a helpful MCA Student AI Assistant."
        return "You are a helpful MCA Student AI Assistant."
