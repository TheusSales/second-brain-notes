"""Camada de abstração para múltiplos provedores de IA.

Cada provedor implementa a interface AIProvider, que recebe um system prompt
e um user prompt e retorna a resposta em texto puro do LLM.

Provedores suportados:
    - groq: Groq API (Llama 3.3 70B) — gratuito
    - openai: OpenAI API (GPT-4o mini)
    - anthropic: Anthropic API (Claude Sonnet)
    - gemini: Google Gemini API (Gemini 2.0 Flash)

Example:
    >>> from backend.ai_providers import get_provider
    >>> provider = get_provider()
    >>> response = await provider.generate("System prompt", "User prompt")
"""

import asyncio
from abc import ABC, abstractmethod

from backend.config import settings


class AIProvider(ABC):
    """Interface base para provedores de IA."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Envia prompt ao LLM e retorna a resposta em texto.

        Args:
            system_prompt: Instrução de sistema para o modelo.
            user_prompt: Mensagem do usuário com o conteúdo.

        Returns:
            Texto da resposta do modelo.
        """


class GroqProvider(AIProvider):
    """Provedor Groq (Llama 3.3 70B via Groq Cloud)."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        import groq as groq_sdk

        def _call():
            client = groq_sdk.Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.groq_model,
                max_tokens=settings.groq_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_call)


class OpenAIProvider(AIProvider):
    """Provedor OpenAI (GPT-4o mini)."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI

        def _call():
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=settings.groq_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content

        return await asyncio.to_thread(_call)


class AnthropicProvider(AIProvider):
    """Provedor Anthropic (Claude Sonnet)."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic

        def _call():
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.groq_max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.content[0].text

        return await asyncio.to_thread(_call)


class GeminiProvider(AIProvider):
    """Provedor Google Gemini (Gemini 2.0 Flash)."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        from google import genai

        def _call():
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=settings.groq_max_tokens,
                ),
            )
            return response.text

        return await asyncio.to_thread(_call)


PROVIDERS: dict[str, type[AIProvider]] = {
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider() -> AIProvider:
    """Retorna a instância do provedor configurado em AI_PROVIDER.

    Returns:
        Instância do provedor de IA selecionado.

    Raises:
        ValueError: Se o provedor configurado não for suportado.
    """
    name = settings.ai_provider
    cls = PROVIDERS.get(name)
    if cls is None:
        supported = ", ".join(PROVIDERS.keys())
        raise ValueError(
            f"Provedor '{name}' não suportado. Opções: {supported}"
        )
    return cls()
