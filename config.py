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
    'gemini': {
        'name': 'Gemini Pro',
        'model_id': 'gemini-pro',
        'max_tokens': 30720,  # ~32k context window
        'temperature': 0.7,
    },
    'chatgpt': {
        'name': 'GPT-4',
        'model_id': 'gpt-4-turbo-preview',
        'max_tokens': 128000,  # 128k context window
        'temperature': 0.7,
    },
    'deepseek': {
        'name': 'DeepSeek Chat',
        'model_id': 'deepseek-chat',
        'max_tokens': 32768,  # 32k context window
        'temperature': 0.7,
    },
    'kimi': {
        'name': 'Kimi',
        'model_id': 'moonshot-v1-32k',
        'max_tokens': 32768,
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
    if GEMINI_API_KEY:
        available.append('gemini')
    if OPENAI_API_KEY:
        available.append('chatgpt')
    if DEEPSEEK_API_KEY:
        available.append('deepseek')
    if KIMI_API_KEY:
        available.append('kimi')
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
