"""Configurações centralizadas do projeto Second Brain Notes.

Todas as variáveis de configuração são lidas de variáveis de ambiente ou do
arquivo `.env` na raiz do projeto. Importe `settings` nos demais módulos.

Roadmap — Multi-provider:
    No futuro, este módulo será expandido para suportar múltiplos provedores de IA
    (Groq, Google Gemini, OpenAI, Anthropic, etc.). O usuário poderá selecionar o
    provedor e fornecer sua própria chave via interface ou variável de ambiente.
    Ver: AI_PROVIDER e as chaves opcionais por provedor abaixo.

Example:
    >>> from backend.config import settings
    >>> print(settings.obsidian_vault_path)
    /home/user/Documents/Obsidian/Vault/Inbox
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente.

    Attributes:
        groq_api_key: Chave de API do Groq (provedor atual).
        obsidian_vault_path: Caminho para a pasta Inbox do vault do Obsidian.
        groq_model: ID do modelo Groq a ser utilizado.
        groq_max_tokens: Número máximo de tokens na resposta.
        httpx_timeout: Timeout em segundos para requisições HTTP externas.
        httpx_max_content_chars: Limite de caracteres do conteúdo de URLs.
        telegram_bot_token: Token do bot do Telegram (opcional).
    """

    groq_api_key: str
    obsidian_vault_path: Path = Path.home() / "Documents/Obsidian/Vault/Inbox"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 4096
    httpx_timeout: float = 30.0
    httpx_max_content_chars: int = 8000
    telegram_bot_token: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
