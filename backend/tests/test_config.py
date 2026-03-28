"""Testes para o módulo de configuração (config.py).

Verifica que as settings são carregadas corretamente das variáveis de ambiente
e que valores obrigatórios e padrões funcionam conforme esperado.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError


class TestSettings:
    """Testes para a classe Settings."""

    def test_loads_groq_api_key_from_env(self, monkeypatch):
        """Settings deve carregar GROQ_API_KEY da variável de ambiente."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
        from backend.config import Settings
        settings = Settings()
        assert settings.groq_api_key == "gsk-test-key"

    def test_default_ai_provider_is_groq(self, monkeypatch):
        """ai_provider deve ter valor padrão 'groq'."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
        from backend.config import Settings
        settings = Settings()
        assert settings.ai_provider == "groq"

    def test_custom_ai_provider_from_env(self, monkeypatch):
        """ai_provider deve ser sobrescrito via variável de ambiente."""
        monkeypatch.setenv("AI_PROVIDER", "openai")
        from backend.config import Settings
        settings = Settings()
        assert settings.ai_provider == "openai"

    def test_default_obsidian_vault_path(self, monkeypatch):
        """obsidian_vault_path deve ter valor padrão correto."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        from backend.config import Settings
        settings = Settings(_env_file="")
        expected = Path.home() / "Documents/Obsidian/Vault/Inbox"
        assert settings.obsidian_vault_path == expected

    def test_custom_obsidian_vault_path_from_env(self, monkeypatch, tmp_path):
        """obsidian_vault_path deve ser sobrescrito via variável de ambiente."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from backend.config import Settings
        settings = Settings()
        assert settings.obsidian_vault_path == tmp_path

    def test_default_groq_model(self, monkeypatch):
        """groq_model deve ter valor padrão 'llama-3.3-70b-versatile'."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
        from backend.config import Settings
        settings = Settings()
        assert settings.groq_model == "llama-3.3-70b-versatile"
