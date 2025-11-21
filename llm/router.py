"""
LLM Router and Provider Abstraction
Provides unified interface for multiple LLM providers
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import config


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, api_key: str, model_config: Dict):
        self.api_key = api_key
        self.model_config = model_config
        self.model_name = model_config['name']
        self.model_id = model_config['model_id']
        self.max_tokens = model_config['max_tokens']
        self.temperature = model_config.get('temperature', 0.7)
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content from prompt"""
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            'name': self.model_name,
            'model_id': self.model_id,
            'max_tokens': self.max_tokens
        }


class GeminiProvider(LLMProvider):
    """Google Gemini provider"""
    
    def __init__(self, api_key: str, model_config: Dict):
        super().__init__(api_key, model_config)
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_id)
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content using Gemini"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': kwargs.get('temperature', self.temperature),
                }
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation failed: {str(e)}")


class ChatGPTProvider(LLMProvider):
    """OpenAI ChatGPT provider"""
    
    def __init__(self, api_key: str, model_config: Dict):
        super().__init__(api_key, model_config)
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content using ChatGPT"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get('temperature', self.temperature),
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"ChatGPT generation failed: {str(e)}")


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider"""
    
    def __init__(self, api_key: str, model_config: Dict):
        super().__init__(api_key, model_config)
        from openai import OpenAI
        # DeepSeek uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1"
        )
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content using DeepSeek"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get('temperature', self.temperature),
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"DeepSeek generation failed: {str(e)}")


class KimiProvider(LLMProvider):
    """Moonshot Kimi provider"""
    
    def __init__(self, api_key: str, model_config: Dict):
        super().__init__(api_key, model_config)
        from openai import OpenAI
        # Kimi uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.moonshot.cn/v1"
        )
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content using Kimi"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get('temperature', self.temperature),
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Kimi generation failed: {str(e)}")


class LLMRouter:
    """Routes requests to appropriate LLM provider"""
    
    def __init__(self):
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available providers based on API keys"""
        if config.GEMINI_API_KEY:
            self.providers['gemini'] = GeminiProvider(
                config.GEMINI_API_KEY,
                config.LLM_MODELS['gemini']
            )
        
        if config.OPENAI_API_KEY:
            self.providers['chatgpt'] = ChatGPTProvider(
                config.OPENAI_API_KEY,
                config.LLM_MODELS['chatgpt']
            )
        
        if config.DEEPSEEK_API_KEY:
            self.providers['deepseek'] = DeepSeekProvider(
                config.DEEPSEEK_API_KEY,
                config.LLM_MODELS['deepseek']
            )
        
        if config.KIMI_API_KEY:
            self.providers['kimi'] = KimiProvider(
                config.KIMI_API_KEY,
                config.LLM_MODELS['kimi']
            )
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        return [
            {
                'id': provider_id,
                **provider.get_model_info()
            }
            for provider_id, provider in self.providers.items()
        ]
    
    def generate(self, provider_id: str, prompt: str, **kwargs) -> str:
        """Generate content using specified provider"""
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not available. Available: {list(self.providers.keys())}")
        
        return self.providers[provider_id].generate(prompt, **kwargs)
    
    def get_max_tokens(self, provider_id: str) -> int:
        """Get max tokens for a provider"""
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not available")
        
        return self.providers[provider_id].max_tokens


# Global router instance
llm_router = LLMRouter()

# Backwards compatibility: alias and wrapper method
class LLMClient:
    """Wrapper for backward compatibility"""
    def __init__(self, router):
        self.router = router
        self.default_provider = 'deepseek'  # Default to deepseek-chat
    
    def generate_text(self, prompt: str, provider_id: str = None, **kwargs) -> str:
        """Generate text using default or specified provider"""
        pid = provider_id or self.default_provider
        # Fallback to first available provider if default not available
        if pid not in self.router.providers and self.router.providers:
            pid = list(self.router.providers.keys())[0]
        return self.router.generate(pid, prompt, **kwargs)

llm_client = LLMClient(llm_router)
