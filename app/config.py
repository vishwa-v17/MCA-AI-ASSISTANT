import os
import json

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mca_assistant.db')
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'smartgpt_config.json')
    PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'system-prompt.txt')
    
    _cached_api_config = None
    
    @classmethod
    def load_api_config(cls):
        if cls._cached_api_config is not None:
            return cls._cached_api_config
            
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, "r") as f:
                    cls._cached_api_config = json.load(f)
                    return cls._cached_api_config
            except Exception:
                pass
        return {}

    @classmethod
    def save_api_config(cls, data):
        with open(cls.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        cls._cached_api_config = data
        
    @classmethod
    def get_system_prompt(cls):
        if os.path.exists(cls.PROMPT_FILE):
            with open(cls.PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return content if content else "You are a helpful MCA Student AI Assistant."
        return "You are a helpful MCA Student AI Assistant."
    # Security settings for uploads
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB per file
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'webp'}
