"""Módulo de geração de notas usando provedores de IA.

Responsável por:
- Buscar conteúdo de URLs externas
- Montar o prompt para o LLM
- Chamar o provedor de IA configurado (Groq, OpenAI, Anthropic, Gemini)
- Parsear a resposta JSON em objetos Pydantic

Example:
    >>> import asyncio
    >>> from backend.note_generator import NoteRequest, generate_note
    >>> request = NoteRequest(text="FastAPI é um framework Python.")
    >>> note = asyncio.run(generate_note(request))
    >>> print(note.titulo)
    Introdução ao FastAPI
"""

import json
import re
import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
import html2text
from pydantic import BaseModel, model_validator

from backend.config import settings
from backend.vault_reader import format_vault_context


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class NoteRequest(BaseModel):
    """Modelo de requisição para criação de nota.

    Attributes:
        text: Texto livre a ser transformado em nota.
        url: URL de uma página web cujo conteúdo será extraído.
        provider: Provedor de IA a usar (override temporário, opcional).

    Raises:
        ValueError: Se nem text nem url forem fornecidos.
    """

    text: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "NoteRequest":
        """Valida que pelo menos text ou url foi fornecido."""
        if not self.text and not self.url:
            raise ValueError("Pelo menos 'text' ou 'url' deve ser fornecido.")
        return self


class Flashcard(BaseModel):
    """Modelo de um flashcard para revisão espaçada.

    Attributes:
        question: Pergunta do flashcard.
        answer: Resposta do flashcard.
    """

    question: str
    answer: str


class GeneratedNote(BaseModel):
    """Nota gerada pelo LLM com todos os campos estruturados.

    Attributes:
        titulo: Título da nota no idioma do conteúdo.
        resumo: Resumo de 2-4 frases capturando a ideia central.
        flashcards: Lista de flashcards para revisão espaçada.
        tags: Lista de 3-6 tags em minúsculas.
        connections: Lista de títulos de notas existentes relacionadas (para [[wikilinks]]).
        fonte: URL da fonte ou 'manual' para texto livre.
        date: Data da criação no formato ISO (YYYY-MM-DD).
        body: Corpo completo da nota em Markdown.
    """

    titulo: str
    resumo: str
    flashcards: list[Flashcard]
    tags: list[str]
    connections: list[str] = []
    fonte: str
    date: str
    body: str


# ---------------------------------------------------------------------------
# Constantes de prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um assistente de "Second Brain". Sua função é transformar qualquer
conteúdo em uma nota de aprendizado estruturada.

IMPORTANTE: Responda APENAS com JSON puro e válido. Sem markdown fences, sem texto
explicativo, sem comentários. Apenas o objeto JSON."""

USER_PROMPT_TEMPLATE = """Transforme o conteúdo abaixo em uma nota de aprendizado.

TIPO DE FONTE: {source_type}
CONTEÚDO:
---
{content}
---
{vault_context}
Retorne um JSON com EXATAMENTE estes campos:
{{
  "titulo": "título conciso no idioma do conteúdo",
  "resumo": "resumo de 2 a 4 frases capturando a ideia central",
  "flashcards": [
    {{"question": "pergunta que testa compreensão", "answer": "resposta objetiva"}},
    ... (entre 3 e 7 flashcards)
  ],
  "tags": ["tag1", "tag2", "tag3"],
  "connections": ["Título da nota existente relacionada", ...],
  "body": "Nota completa em Markdown com títulos, listas e exemplos. Mínimo 150 palavras. Inclua uma seção '## Conexões' no final com [[wikilinks]] para as notas relacionadas."
}}

Regras:
- titulo, resumo, tags e body devem estar no idioma do conteúdo
- Perguntas dos flashcards devem testar compreensão, não apenas memorização
- Tags em minúsculas, sem hashtag, conceitos gerais (3 a 6 tags)
- connections: lista com títulos EXATOS de notas existentes que se relacionam com este conteúdo (somente notas da lista acima, pode ser vazia se nenhuma for relevante)
- body deve incluir conceitos-chave, exemplos e uma seção "## Conexões" no final com links [[Título da Nota]] para cada conexão sugerida"""


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

async def fetch_url_content(url: str) -> str:
    """Busca uma URL e retorna seu conteúdo como texto limpo.

    Remove elementos de navegação, scripts e estilos antes de converter
    para texto, limitando o tamanho para caber no contexto do prompt.

    Args:
        url: URL da página a ser buscada.

    Returns:
        Texto limpo da página, limitado a `settings.httpx_max_content_chars` caracteres.

    Raises:
        httpx.HTTPStatusError: Se a resposta HTTP indicar erro (4xx, 5xx).
        httpx.RequestError: Em caso de falha de rede ou timeout.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SecondBrainBot/1.0)"}
    async with httpx.AsyncClient(timeout=settings.httpx_timeout) as client:
        response = await client.get(url, follow_redirects=True, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    clean_text = converter.handle(str(soup))

    return clean_text[: settings.httpx_max_content_chars]


def parse_llm_response(raw: str, fonte: str, date: str) -> GeneratedNote:
    """Parseia a resposta JSON do LLM em um objeto GeneratedNote.

    Trata o caso em que o modelo envolve o JSON em markdown fences (```json...```),
    removendo-as antes do parse.

    Args:
        raw: String com o conteúdo retornado pelo LLM.
        fonte: URL da fonte ou 'manual'.
        date: Data da criação no formato ISO (YYYY-MM-DD).

    Returns:
        Objeto GeneratedNote preenchido.

    Raises:
        json.JSONDecodeError: Se o conteúdo não for JSON válido após limpeza.
        pydantic.ValidationError: Se os campos obrigatórios estiverem ausentes.
    """
    cleaned = raw.strip()

    # Remove markdown fences se presentes (```json ... ```)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    # Extrai o objeto JSON pelo primeiro { e último } — protege contra
    # texto introdutório ou explicativo que o modelo possa adicionar
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start: end + 1]

    # strict=False permite caracteres de controle (ex: newlines literais) dentro
    # de strings JSON — comportamento comum em modelos open-source como Llama
    data = json.loads(cleaned, strict=False)

    return GeneratedNote(
        titulo=data["titulo"],
        resumo=data["resumo"],
        flashcards=[Flashcard(**fc) for fc in data.get("flashcards", [])],
        tags=data["tags"],
        connections=data.get("connections", []),
        fonte=fonte,
        date=date,
        body=data["body"],
    )


async def generate_note(request: NoteRequest) -> GeneratedNote:
    """Gera uma nota estruturada a partir de texto ou URL usando o provedor de IA configurado.

    Se `request.url` for fornecido, busca o conteúdo da página antes de
    chamar o LLM. O provedor é selecionado via a variável AI_PROVIDER.

    Args:
        request: Objeto NoteRequest com text ou url preenchido.

    Returns:
        Objeto GeneratedNote com todos os campos preenchidos.

    Raises:
        httpx.HTTPStatusError: Se a URL fornecida retornar erro HTTP.
        httpx.RequestError: Em caso de falha de rede ao buscar URL.
        json.JSONDecodeError: Se o LLM retornar JSON malformado.
    """
    from backend.ai_providers import get_provider

    provider_override = request.provider if hasattr(request, "provider") else None

    if request.url:
        content = await fetch_url_content(request.url)
        fonte = request.url
        source_type = f"url: {request.url}"
    else:
        content = request.text
        fonte = "manual"
        source_type = "texto manual"

    today = datetime.date.today().isoformat()

    vault_context = format_vault_context()
    if vault_context:
        vault_context = f"\n{vault_context}\n"
    else:
        vault_context = ""

    user_prompt = USER_PROMPT_TEMPLATE.format(
        source_type=source_type,
        content=content,
        vault_context=vault_context,
    )

    provider = get_provider(provider_override)
    raw_response = await provider.generate(SYSTEM_PROMPT, user_prompt)
    return parse_llm_response(raw_response, fonte=fonte, date=today)
