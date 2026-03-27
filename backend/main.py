"""Aplicação FastAPI principal do projeto Second Brain Notes.

Expõe os endpoints HTTP para criação de notas e verificação de saúde.
Orquestra o fluxo: receber requisição → gerar nota com Claude → salvar no Obsidian.

Endpoints:
    POST /notes  — Cria uma nova nota a partir de texto ou URL.
    GET  /health — Verifica se o serviço está em funcionamento.

Example:
    Iniciando o servidor em modo desenvolvimento:

        uvicorn backend.main:app --reload --port 8000

    Testando com curl:

        curl -X POST http://localhost:8000/notes \\
          -H "Content-Type: application/json" \\
          -d '{"text": "FastAPI é um framework Python de alta performance."}'
"""

import json

import groq as groq_sdk
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.note_generator import Flashcard, GeneratedNote, NoteRequest, generate_note
from backend.obsidian_writer import render_note, save_note


# ---------------------------------------------------------------------------
# Modelos de resposta
# ---------------------------------------------------------------------------

class NoteResponse(BaseModel):
    """Resposta retornada após a criação de uma nota.

    Attributes:
        titulo: Título da nota gerada.
        resumo: Resumo de 2-4 frases.
        tags: Lista de tags geradas.
        flashcards: Lista de flashcards para revisão.
        fonte: URL da fonte ou 'manual'.
        date: Data de criação no formato ISO.
        file_path: Caminho absoluto do arquivo .md criado.
        markdown_content: Conteúdo completo do arquivo .md.
    """

    titulo: str
    resumo: str
    tags: list[str]
    flashcards: list[Flashcard]
    fonte: str
    date: str
    file_path: str
    markdown_content: str


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Second Brain Notes API",
    description=(
        "Gera notas de aprendizado estruturadas no formato Obsidian "
        "a partir de texto livre ou URLs, usando a Claude API."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/notes",
    response_model=NoteResponse,
    status_code=201,
    summary="Criar nova nota",
    description=(
        "Recebe texto livre ou URL, chama o Claude para gerar uma nota "
        "estruturada em Markdown e salva no vault do Obsidian."
    ),
)
async def create_note(request: NoteRequest) -> NoteResponse:
    """Cria uma nova nota estruturada e salva no vault do Obsidian.

    Args:
        request: Corpo da requisição com `text` ou `url`.

    Returns:
        NoteResponse com os dados da nota criada e o caminho do arquivo.

    Raises:
        HTTPException 422: Se a URL fornecida for inacessível.
        HTTPException 502: Se a API do Claude retornar um erro.
    """
    try:
        note: GeneratedNote = await generate_note(request)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Falha ao buscar URL: status HTTP {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Erro de rede ao buscar URL: {str(exc)}",
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="O LLM retornou JSON malformado. Tente novamente.",
        )
    except groq_sdk.APIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erro na API do Groq: {str(exc)}",
        )

    file_path = save_note(note)
    markdown_content = render_note(note)

    return NoteResponse(
        titulo=note.titulo,
        resumo=note.resumo,
        tags=note.tags,
        flashcards=note.flashcards,
        fonte=note.fonte,
        date=note.date,
        file_path=str(file_path),
        markdown_content=markdown_content,
    )


@app.get(
    "/health",
    summary="Verificar saúde do serviço",
    description="Retorna o status do serviço e o caminho do vault configurado.",
)
def health() -> dict:
    """Verifica se o serviço está em funcionamento.

    Returns:
        Dicionário com `status` ('ok') e `vault_path` configurado.
    """
    return {
        "status": "ok",
        "vault_path": str(settings.obsidian_vault_path),
    }
