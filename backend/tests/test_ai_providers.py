"""Testes para o módulo ai_providers.py.

Verifica a seleção de provedores, a interface de geração e o tratamento
de provedores inválidos. Todas as chamadas a APIs externas são mockadas.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGetProvider:
    """Testes para a função get_provider."""

    def test_returns_groq_provider(self, monkeypatch):
        """get_provider deve retornar GroqProvider quando AI_PROVIDER=groq."""
        monkeypatch.setenv("AI_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test")
        from backend.config import Settings
        with patch("backend.ai_providers.settings", Settings()):
            from backend.ai_providers import get_provider, GroqProvider
            provider = get_provider()
            assert isinstance(provider, GroqProvider)

    def test_returns_openai_provider(self, monkeypatch):
        """get_provider deve retornar OpenAIProvider quando AI_PROVIDER=openai."""
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("GROQ_API_KEY", "")
        from backend.config import Settings
        with patch("backend.ai_providers.settings", Settings()):
            from backend.ai_providers import get_provider, OpenAIProvider
            provider = get_provider()
            assert isinstance(provider, OpenAIProvider)

    def test_returns_anthropic_provider(self, monkeypatch):
        """get_provider deve retornar AnthropicProvider quando AI_PROVIDER=anthropic."""
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.setenv("GROQ_API_KEY", "")
        from backend.config import Settings
        with patch("backend.ai_providers.settings", Settings()):
            from backend.ai_providers import get_provider, AnthropicProvider
            provider = get_provider()
            assert isinstance(provider, AnthropicProvider)

    def test_returns_gemini_provider(self, monkeypatch):
        """get_provider deve retornar GeminiProvider quando AI_PROVIDER=gemini."""
        monkeypatch.setenv("AI_PROVIDER", "gemini")
        monkeypatch.setenv("GROQ_API_KEY", "")
        from backend.config import Settings
        with patch("backend.ai_providers.settings", Settings()):
            from backend.ai_providers import get_provider, GeminiProvider
            provider = get_provider()
            assert isinstance(provider, GeminiProvider)

    def test_raises_on_invalid_provider(self, monkeypatch):
        """get_provider deve lançar ValueError para provedor desconhecido."""
        monkeypatch.setenv("AI_PROVIDER", "inexistente")
        monkeypatch.setenv("GROQ_API_KEY", "")
        from backend.config import Settings
        with patch("backend.ai_providers.settings", Settings()):
            from backend.ai_providers import get_provider
            with pytest.raises(ValueError, match="inexistente"):
                get_provider()


class TestGroqProvider:
    """Testes para o GroqProvider."""

    @pytest.mark.asyncio
    async def test_generate_calls_groq_api(self, monkeypatch):
        """GroqProvider.generate deve chamar a API do Groq e retornar texto."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from backend.ai_providers import GroqProvider

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "resposta do llm"

        with patch("backend.ai_providers.settings") as mock_settings:
            mock_settings.groq_api_key = "test-key"
            mock_settings.groq_model = "llama-3.3-70b-versatile"
            mock_settings.groq_max_tokens = 4096
            with patch("groq.Groq") as MockGroq:
                MockGroq.return_value.chat.completions.create.return_value = mock_response
                provider = GroqProvider()
                result = await provider.generate("system", "user")

        assert result == "resposta do llm"


class TestOpenAIProvider:
    """Testes para o OpenAIProvider."""

    @pytest.mark.asyncio
    async def test_generate_calls_openai_api(self):
        """OpenAIProvider.generate deve chamar a API da OpenAI e retornar texto."""
        from backend.ai_providers import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "resposta openai"

        with patch("backend.ai_providers.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.groq_max_tokens = 4096
            with patch("openai.OpenAI") as MockOpenAI:
                MockOpenAI.return_value.chat.completions.create.return_value = mock_response
                provider = OpenAIProvider()
                result = await provider.generate("system", "user")

        assert result == "resposta openai"


class TestAnthropicProvider:
    """Testes para o AnthropicProvider."""

    @pytest.mark.asyncio
    async def test_generate_calls_anthropic_api(self):
        """AnthropicProvider.generate deve chamar a API da Anthropic e retornar texto."""
        from backend.ai_providers import AnthropicProvider

        mock_response = MagicMock()
        mock_response.content[0].text = "resposta anthropic"

        with patch("backend.ai_providers.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            mock_settings.groq_max_tokens = 4096
            with patch("anthropic.Anthropic") as MockAnthropic:
                MockAnthropic.return_value.messages.create.return_value = mock_response
                provider = AnthropicProvider()
                result = await provider.generate("system", "user")

        assert result == "resposta anthropic"


class TestGeminiProvider:
    """Testes para o GeminiProvider."""

    @pytest.mark.asyncio
    async def test_generate_calls_gemini_api(self):
        """GeminiProvider.generate deve chamar a API do Gemini e retornar texto."""
        from backend.ai_providers import GeminiProvider

        mock_response = MagicMock()
        mock_response.text = "resposta gemini"

        with patch("backend.ai_providers.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-key"
            mock_settings.gemini_model = "gemini-2.0-flash"
            mock_settings.groq_max_tokens = 4096
            with patch("google.genai.Client") as MockClient:
                MockClient.return_value.models.generate_content.return_value = mock_response
                provider = GeminiProvider()
                result = await provider.generate("system", "user")

        assert result == "resposta gemini"
