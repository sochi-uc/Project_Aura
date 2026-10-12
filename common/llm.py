import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from common.config import get_config

logger = logging.getLogger("AuraLLM")


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers in Project Aura.
    Decouples business logic from specific cloud providers (Gemini, Groq, OpenAI, etc.).
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        is_json: bool = False,
    ) -> str:
        """
        Generate text completion from the provider.
        """
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini implementation using official google-genai SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        cfg = get_config()
        self.api_key = api_key or cfg.gemini_api_key
        self.model = model or cfg.gemini_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                logger.error("GEMINI_API_KEY is not set in environment or configuration!")
                raise ValueError("GEMINI_API_KEY is required for GeminiProvider.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        is_json: bool = False,
    ) -> str:
        from google.genai import types
        client = self._get_client()

        config_args: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if is_json:
            config_args["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_args)

        for attempt in range(5):
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                try:
                    finish_reason = response.candidates[0].finish_reason
                    logger.debug(f"Gemini finish_reason: {finish_reason}")
                except Exception:
                    pass
                return response.text

            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "503" in err_str:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(
                        f"Gemini rate limit / overload. Retrying in {wait_time:.2f}s (Attempt {attempt+1}/5)..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Fatal Gemini Error: {e}")
                    raise e

        raise RuntimeError("Failed to obtain response from Gemini after 5 attempts.")


class GroqProvider(BaseLLMProvider):
    """
    Groq high-speed inference provider (e.g. Llama 3.3).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        cfg = get_config()
        self.api_key = api_key or cfg.groq_api_key
        self.model = model or cfg.groq_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                logger.error("GROQ_API_KEY is not set in environment or configuration!")
                raise ValueError("GROQ_API_KEY is required for GroqProvider.")
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        is_json: bool = False,
    ) -> str:
        client = self._get_client()

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if is_json:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(5):
            try:
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(
                        f"Groq rate limit encountered. Retrying in {wait_time:.2f}s (Attempt {attempt+1}/5)..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Fatal Groq Error: {e}")
                    raise e

        raise RuntimeError("Failed to obtain response from Groq after 5 attempts.")


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Generic OpenAI-compatible provider (OpenAI, LocalAI, Ollama, vLLM, OpenRouter).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        cfg = get_config()
        self.api_key = api_key or cfg.openai_api_key or "sk-dummy"
        self.base_url = (base_url or cfg.openai_api_base or "https://api.openai.com/v1").rstrip("/")
        self.model = model or cfg.openai_model

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        is_json: bool = False,
    ) -> str:
        import httpx

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if is_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(5):
                try:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if resp.status_code == 429:
                        wait_time = (2 ** attempt) + random.uniform(1, 3)
                        await asyncio.sleep(wait_time)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                except Exception as e:
                    if attempt == 4:
                        logger.error(f"Fatal OpenAI-compatible Error: {e}")
                        raise e
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Failed to obtain response from OpenAI-compatible provider.")


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for unit testing and CI without calling network APIs.
    """

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        is_json: bool = False,
    ) -> str:
        if is_json:
            return json.dumps({
                "results": [
                    {"id": "1", "relevant": True, "reason": "Mock match"}
                ]
            })
        return f"[MockLLMResponse] System: {system_instruction} | Prompt: {prompt[:80]}"


_provider_cache: Dict[str, BaseLLMProvider] = {}


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseLLMProvider:
    """
    Factory to retrieve an LLM provider instance based on name or environment configuration.
    """
    cfg = get_config()
    target_provider = (provider_name or cfg.llm_provider).lower()
    cache_key = f"{target_provider}:{model_name or 'default'}"

    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    if target_provider == "gemini":
        instance = GeminiProvider(model=model_name)
    elif target_provider == "groq":
        instance = GroqProvider(model=model_name)
    elif target_provider in ("openai", "openai_compatible", "local_llm", "vllm", "ollama"):
        instance = OpenAICompatibleProvider(model=model_name)
    elif target_provider in ("mock", "test"):
        instance = MockLLMProvider()
    else:
        logger.warning(f"Unknown LLM provider '{target_provider}'. Defaulting to GeminiProvider.")
        instance = GeminiProvider(model=model_name)

    _provider_cache[cache_key] = instance
    return instance


async def call_llm(
    prompt: str,
    system_instruction: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    is_json: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generic entrypoint for LLM text completion.
    Uses the configured default provider unless explicitly overridden.
    """
    llm = get_llm_provider(provider_name=provider, model_name=model)
    return await llm.generate(
        prompt=prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        is_json=is_json,
    )


async def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    is_json: bool = False,
) -> str:
    """
    Backward-compatible wrapper for existing callers.
    Routes to the configured LLM provider.
    """
    return await call_llm(
        prompt=prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        is_json=is_json,
    )
