"""
Ollama client service for LIT TUI.

This module provides a clean interface to the Ollama API, handling
model management, chat completion, and streaming responses.
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, List, Optional, Any

import ollama
from ollama import AsyncClient

from ..config import Config


logger = logging.getLogger(__name__)


class OllamaModel:
    """Represents an Ollama model."""
    
    def __init__(self, name: str, size: int = 0, digest: str = "", details: Optional[Dict] = None):
        self.name = name
        self.size = size
        self.digest = digest
        self.details = details or {}
        
    @property
    def display_name(self) -> str:
        """Get a user-friendly display name."""
        # Remove :latest suffix for cleaner display
        name = self.name.replace(":latest", "")
        
        # Capitalize first letter
        return name.capitalize()
    
    @property
    def size_mb(self) -> float:
        """Get model size in MB."""
        return self.size / (1024 * 1024)
    
    def __str__(self) -> str:
        return f"{self.display_name} ({self.size_mb:.1f}MB)"


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, config: Config):
        """Initialize Ollama client."""
        self.config = config
        self.client = AsyncClient(host=config.ollama.host)
        self._models_cache: Optional[List[OllamaModel]] = None
        self._cache_time: Optional[float] = None
        
    async def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            await self.client.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama server not available: {e}")
            return False
    
    async def get_models(self, force_refresh: bool = False) -> List[OllamaModel]:
        """Get list of available models."""
        # Use cache if recent (within 30 seconds)
        current_time = asyncio.get_event_loop().time()
        if (not force_refresh and 
            self._models_cache is not None and 
            self._cache_time is not None and 
            current_time - self._cache_time < 30):
            return self._models_cache
        
        try:
            response = await self.client.list()
            models = []
            
            for model_data in response.get('models', []):
                model = OllamaModel(
                    name=model_data.get('name', ''),
                    size=model_data.get('size', 0),
                    digest=model_data.get('digest', ''),
                    details=model_data.get('details', {})
                )
                models.append(model)
            
            # Cache the results
            self._models_cache = models
            self._cache_time = current_time
            
            logger.info(f"Found {len(models)} Ollama models")
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            return []
    
    async def get_default_model(self) -> Optional[str]:
        """Get the default model to use."""
        # Use configured default if set
        if self.config.ollama.default_model:
            return self.config.ollama.default_model
        
        # Otherwise, try to find a good default
        models = await self.get_models()
        if not models:
            return None
        
        # Prefer llama2 or llama3 if available
        for model in models:
            if 'llama' in model.name.lower():
                return model.name
        
        # Otherwise use the first available model
        return models[0].name
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate chat completion with streaming support.
        
        Args:
            model: Model name to use
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
            **kwargs: Additional parameters for the API
        
        Yields:
            Response text chunks if streaming, otherwise yields complete response
        """
        try:
            if stream:
                async for chunk in self._stream_chat(model, messages, **kwargs):
                    yield chunk
            else:
                response = await self._complete_chat(model, messages, **kwargs)
                yield response
                
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            yield f"Error: {e}"
    
    async def _stream_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat completion."""
        try:
            async for chunk in await self.client.chat(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            ):
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    if content:  # Only yield non-empty content
                        yield content
                        
        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            yield f"\nError: {e}"
    
    async def _complete_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Complete chat without streaming."""
        try:
            response = await self.client.chat(
                model=model,
                messages=messages,
                stream=False,
                **kwargs
            )
            
            if 'message' in response and 'content' in response['message']:
                return response['message']['content']
            else:
                return "No response content received"
                
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            return f"Error: {e}"
    
    async def pull_model(self, model_name: str) -> AsyncIterator[str]:
        """
        Pull/download a model with progress updates.
        
        Args:
            model_name: Name of model to pull
            
        Yields:
            Progress updates during download
        """
        try:
            async for progress in await self.client.pull(model_name, stream=True):
                if 'status' in progress:
                    yield progress['status']
                    
        except Exception as e:
            logger.error(f"Model pull failed: {e}")
            yield f"Error pulling model: {e}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health information about the Ollama service."""
        try:
            models = await self.get_models()
            return {
                "status": "healthy",
                "available": True,
                "model_count": len(models),
                "models": [m.name for m in models[:5]],  # First 5 models
                "host": self.config.ollama.host
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "available": False,
                "error": str(e),
                "host": self.config.ollama.host
            }
