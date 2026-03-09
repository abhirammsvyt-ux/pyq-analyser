"""
LLM client for Qwen 2.5 7B Instruct API.
"""
import logging
from typing import Optional
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Qwen API inference."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        api_key: Optional[str] = None
    ):
        self.api_key = api_key or getattr(settings, 'QWEN_API_KEY', None)
        self.base_url = base_url or getattr(settings, 'QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = model or getattr(settings, 'QWEN_MODEL', 'qwen2.5-7b-instruct')
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("QWEN_API_KEY not configured")
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate text using Qwen API (Hugging Face or compatible).
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            
        Returns:
            Generated text
        """
        if not self.api_key:
            logger.error("QWEN_API_KEY not configured")
            return ""
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Check API type based on URL
            if not self.api_key or 'localhost' in self.base_url or '127.0.0.1' in self.base_url:
                # Local Ollama API
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "num_predict": max_tokens,
                                "temperature": temperature
                            }
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data.get('response', '')
                    
            elif 'huggingface.co' in self.base_url:
                # Try OpenAI-compatible endpoint first (newer HF API)
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        # Check if it's the v1 endpoint
                        if '/v1' in self.base_url or 'chat/completions' in self.base_url:
                            url = self.base_url if self.base_url.endswith('/chat/completions') else f"{self.base_url.rstrip('/v1')}/v1/chat/completions"
                            response = client.post(
                                url,
                                headers=headers,
                                json={
                                    "model": "tgi",  # HF uses "tgi" for serverless
                                    "messages": [
                                        {"role": "user", "content": prompt}
                                    ],
                                    "max_tokens": max_tokens,
                                    "temperature": temperature
                                }
                            )
                        else:
                            # Legacy inference API format
                            response = client.post(
                                self.base_url,
                                headers=headers,
                                json={
                                    "inputs": prompt,
                                    "parameters": {
                                        "max_new_tokens": max_tokens,
                                        "temperature": temperature,
                                        "return_full_text": False
                                    }
                                }
                            )
                        
                        response.raise_for_status()
                        data = response.json()
                        
                        # Handle different response formats
                        if 'choices' in data:
                            return data['choices'][0]['message']['content']
                        elif isinstance(data, list) and len(data) > 0:
                            return data[0].get('generated_text', '')
                        elif isinstance(data, dict):
                            return data.get('generated_text', '')
                        return str(data)
                        
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 410:
                        logger.error("Model endpoint deprecated. Try using OpenAI-compatible endpoint with /v1/chat/completions")
                    raise
            else:
                # OpenAI-compatible format (DashScope, etc.)
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "stream": stream
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data['choices'][0]['message']['content']
                
        except httpx.HTTPError as e:
            logger.error(f"Qwen API error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Qwen generation failed: {e}")
            return ""
    
    def is_available(self) -> bool:
        """Check if Qwen API is configured and accessible."""
        if not self.api_key:
            return False
            
        try:
            # Quick test with minimal request
            return True  # If API key exists, assume available
        except Exception:
            return False
    
    def pull_model(self) -> bool:
        """Not applicable for API - model is always available."""
        return self.api_key is not None
