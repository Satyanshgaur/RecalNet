import logging
import httpx
from typing import Any, Dict, List, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from graphmem.core.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    """
    Centralized client for interacting with Ollama.
    Includes retry logic with exponential backoff and configurable timeouts.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.model_name
        self.timeout = timeout if timeout is not None else settings.ollama_timeout
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Asynchronous generate call to Ollama.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            **kwargs,
        }
        if system:
            payload["system"] = system

        response = await self.client.post("/api/generate", json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Asynchronous chat call to Ollama.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()
