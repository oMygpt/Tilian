"""
Configuration module for the Intelligent Textbook Corpus Generation Platform
Loads settings from environment variables and provides configuration constants
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = DATA_DIR / 'uploads'
PARSED_DIR = DATA_DIR / 'parsed'
EXPORT_DIR = DATA_DIR / 'exports'

# Create directories if they don't exist
for directory in [DATA_DIR, UPLOAD_DIR, PARSED_DIR, EXPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database configuration
DATABASE_PATH = DATA_DIR / 'corpus.db'

# MinerU API configuration
MINERU_API_KEY = os.getenv('MINERU_API_KEY', '')
MINERU_API_URL = os.getenv('MINERU_API_URL', 'https://mineru.net/api/v4')
# MinerU file size limits (in MB) - reference their documentation
MINERU_MAX_FILE_SIZE = int(os.getenv('MINERU_MAX_FILE_SIZE', 200))  # MB (200MB max per official docs)
# If file is larger, we'll need to split it
PDF_SPLIT_SIZE = int(os.getenv('PDF_SPLIT_SIZE', 180))  # MB, slightly smaller than max

# LLM API Keys - load from .env
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
KIMI_API_KEY = os.getenv('KIMI_API_KEY', '')

# LLM Model configurations
LLM_MODELS = {
    # Gemini Models
    'gemini-pro-2.5': {
        'provider': 'gemini',
        'name': 'Gemini Pro 2.5',
        'model_id': 'gemini-2.5-pro',
        'max_tokens': 1000000, # 1M context window
        'temperature': 0.7,
    },
    'gemini-pro-3.0': {
        'provider': 'gemini',
        'name': 'Gemini Pro 3.0',
        'model_id': 'gemini-3.0-pro',
        'max_tokens': 2000000, # 2M context window
        'temperature': 0.7,
    },
    
    # OpenAI Models
    'gpt-5.1': {
        'provider': 'chatgpt',
        'name': 'GPT-5.1',
        'model_id': 'gpt-5.1-preview',
        'max_tokens': 400000, # 400k context window
        'temperature': 0.7,
    },
    'gpt-4o': {
        'provider': 'chatgpt',
        'name': 'GPT-4o',
        'model_id': 'gpt-4o',
        'max_tokens': 128000, # 128k context window
        'temperature': 0.7,
    },
    
    # DeepSeek Models
    'deepseek-v3': {
        'provider': 'deepseek',
        'name': 'DeepSeek V3 Chat',
        'model_id': 'deepseek-chat',
        'max_tokens': 64000, # 64k context window (conservative estimate for chat)
        'temperature': 0.7,
    },
    
    # Kimi Models
    'kimi-k2': {
        'provider': 'kimi',
        'name': 'Kimi K2',
        'model_id': 'moonshot-v1-128k', # Using stable alias, assuming K2 maps to this or newer
        'max_tokens': 256000, # 256k context window
        'temperature': 0.7,
    }
}

# Flask configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = FLASK_ENV == 'development'

# File upload settings
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'md', 'txt', 'epub'}

# Background task settings
PARSE_TASK_TIMEOUT = int(os.getenv('PARSE_TASK_TIMEOUT', 3600))  # 1 hour default

# Token counting settings
# Safety margin: if chapter exceeds this percentage of max_tokens, suggest splitting
TOKEN_THRESHOLD_PERCENTAGE = 0.8

# Export settings
EXPORT_ENCODING = 'utf-8-sig'  # UTF-8 with BOM for Excel compatibility

def get_available_models():
    """
    Returns a list of available LLM models based on configured API keys
    """
    available = []
    for model_key, model_config in LLM_MODELS.items():
        provider = model_config.get('provider')
        if provider == 'gemini' and GEMINI_API_KEY:
            available.append(model_key)
        elif provider == 'chatgpt' and OPENAI_API_KEY:
            available.append(model_key)
        elif provider == 'deepseek' and DEEPSEEK_API_KEY:
            available.append(model_key)
        elif provider == 'kimi' and KIMI_API_KEY:
            available.append(model_key)
            
    return available

def validate_config():
    """
    Validates that required configuration is present
    Raises ValueError if critical settings are missing
    """
    errors = []
    
    if not MINERU_API_KEY:
        errors.append("MINERU_API_KEY is not set in .env file")
    
    available_models = get_available_models()
    if not available_models:
        errors.append("No LLM API keys configured. At least one is required.")
    
    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  - {err}" for err in errors)
        )
    
    return True
