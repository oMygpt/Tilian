
import sys
import os
sys.path.append(os.getcwd())

from config import get_available_models, LLM_MODELS

def check_models():
    print("Checking available models...")
    available = get_available_models()
    print(f"Available models: {available}")
    
    volc_models = [m for m in available if LLM_MODELS[m]['provider'] == 'volcengine']
    if volc_models:
        print(f"Volcengine models found: {volc_models}")
    else:
        print("No Volcengine models found. Check if VOLCENGINE_API_KEY is set in .env")

if __name__ == "__main__":
    check_models()
