"""Aplicação FastAPI principal do projeto Second Brain Notes.

Expõe os endpoints HTTP para geração, salvamento e criação de notas.

Endpoints:
    POST /notes/generate — Gera preview da nota sem salvar.
    POST /notes/save     — Salva uma nota previamente gerada no vault.
    POST /notes          — Gera e salva em um passo (retrocompatível).
    GET  /health         — Verifica se o serviço está em funcionamento.

Example:
    Iniciando o servidor em modo desenvolvimento:

        uvicorn backend.main:app --reload --port 8001

    Fluxo de preview:

        # 1. Gerar preview
        curl -X POST http://localhost:8001/notes/generate \\
          -H "Content-Type: application/json" \\
          -d '{"text": "FastAPI é um framework Python."}'

        # 2. Salvar (enviar o JSON retornado no passo anterior)
        curl -X POST http://localhost:8001/notes/save \\
          -H "Content-Type: application/json" \\
          -d '<json da nota gerada>'
"""

import json
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from slugify import slugify

from backend.ai_providers import PROVIDERS
from backend.anki_exporter import AnkiExportRequest, export_csv
from backend.config import settings
from backend.note_generator import Flashcard, GeneratedNote, NoteRequest, generate_note
from backend.obsidian_writer import render_note, save_note

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ---------------------------------------------------------------------------
# Modelos de resposta
# ---------------------------------------------------------------------------

class GenerateResponse(BaseModel):
    """Resposta de preview — nota gerada mas ainda não salva.

    Attributes:
        titulo: Título da nota gerada.
        resumo: Resumo de 2-4 frases.
        tags: Lista de tags geradas.
        flashcards: Lista de flashcards para revisão.
        connections: Lista de títulos de notas relacionadas no vault.
        fonte: URL da fonte ou 'manual'.
        date: Data de criação no formato ISO.
        body: Corpo da nota em Markdown.
        markdown_content: Conteúdo completo do arquivo .md (frontmatter + body).
    """

    titulo: str
    resumo: str
    tags: list[str]
    flashcards: list[Flashcard]
    connections: list[str]
    fonte: str
    date: str
    body: str
    markdown_content: str


class SaveResponse(BaseModel):
    """Resposta após salvar a nota no vault.

    Attributes:
        file_path: Caminho absoluto do arquivo .md criado.
        titulo: Título da nota salva.
    """

    file_path: str
    titulo: str


class NoteResponse(BaseModel):
    """Resposta completa — nota gerada e salva (retrocompatibilidade).

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
        "a partir de texto livre ou URLs, usando IA (Groq/Llama)."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _generate_note_or_raise(request: NoteRequest) -> GeneratedNote:
    """Gera nota via LLM, convertendo exceções em HTTPException.

    Args:
        request: Corpo da requisição com `text` ou `url`.

    Returns:
        GeneratedNote com todos os campos preenchidos.

    Raises:
        HTTPException 422: Se a URL fornecida for inacessível.
        HTTPException 502: Se a API do LLM retornar um erro.
    """
    try:
        return await generate_note(request)
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
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erro na API do provedor de IA: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/notes/generate",
    response_model=GenerateResponse,
    summary="Gerar preview da nota",
    description="Gera uma nota estruturada via IA para pré-visualização, sem salvar no vault.",
)
async def generate_preview(request: NoteRequest) -> GenerateResponse:
    """Gera uma nota para preview sem salvar no vault do Obsidian.

    Args:
        request: Corpo da requisição com `text` ou `url`.

    Returns:
        GenerateResponse com os dados da nota e o conteúdo Markdown renderizado.
    """
    note = await _generate_note_or_raise(request)
    markdown_content = render_note(note)

    return GenerateResponse(
        titulo=note.titulo,
        resumo=note.resumo,
        tags=note.tags,
        flashcards=note.flashcards,
        connections=note.connections,
        fonte=note.fonte,
        date=note.date,
        body=note.body,
        markdown_content=markdown_content,
    )


@app.post(
    "/notes/save",
    response_model=SaveResponse,
    status_code=201,
    summary="Salvar nota no vault",
    description="Recebe uma nota previamente gerada e salva como arquivo .md no vault do Obsidian.",
)
def save_generated_note(note: GeneratedNote) -> SaveResponse:
    """Salva uma nota previamente gerada no vault do Obsidian.

    Args:
        note: Objeto GeneratedNote com todos os campos preenchidos.

    Returns:
        SaveResponse com o caminho do arquivo criado.
    """
    file_path = save_note(note)
    return SaveResponse(
        file_path=str(file_path),
        titulo=note.titulo,
    )


@app.post(
    "/notes",
    response_model=NoteResponse,
    status_code=201,
    summary="Criar nota (gerar + salvar)",
    description="Gera e salva a nota em um único passo. Mantido para retrocompatibilidade.",
)
async def create_note(request: NoteRequest) -> NoteResponse:
    """Gera e salva uma nota em um único passo.

    Args:
        request: Corpo da requisição com `text` ou `url`.

    Returns:
        NoteResponse com os dados da nota criada e o caminho do arquivo.
    """
    note = await _generate_note_or_raise(request)
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


@app.post(
    "/notes/export-anki",
    summary="Exportar flashcards para Anki",
    description="Gera um arquivo texto (TSV/CSV) compatível com o importador do Anki.",
)
def export_anki(request: AnkiExportRequest) -> PlainTextResponse:
    """Gera arquivo de flashcards para importação no Anki.

    Args:
        request: Flashcards, deck, tags e separador.

    Returns:
        PlainTextResponse com o arquivo para download.
    """
    content = export_csv(request)
    filename = slugify(request.deck, max_length=40, word_boundary=True) or "anki-export"
    return PlainTextResponse(
        content=content,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.txt"',
        },
    )


@app.get(
    "/providers",
    summary="Listar provedores de IA disponíveis",
    description="Retorna os provedores suportados e qual está ativo.",
)
def list_providers() -> dict:
    """Retorna os provedores de IA disponíveis e o ativo."""
    return {
        "active": settings.ai_provider,
        "available": list(PROVIDERS.keys()),
    }


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


# ---------------------------------------------------------------------------
# Frontend — arquivos estáticos
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve a página principal do frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
