"""Testes de integração para os endpoints da API FastAPI (main.py).

Utiliza o TestClient do FastAPI/httpx para testar os endpoints sem precisar
subir um servidor real. As chamadas ao LLM e ao filesystem são mockadas.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.note_generator import Flashcard, GeneratedNote


@pytest.fixture
def sample_note():
    """Nota de exemplo retornada pelo mock do generate_note."""
    return GeneratedNote(
        titulo="FastAPI Fundamentos",
        resumo="FastAPI é um framework moderno para construção de APIs Python.",
        flashcards=[
            Flashcard(question="O que é FastAPI?", answer="Framework Python para APIs.")
        ],
        tags=["python", "fastapi", "api"],
        fonte="manual",
        date="2026-03-26",
        body="## FastAPI\n\nFastAPI permite criar APIs com validação automática.",
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    """TestClient com variáveis de ambiente configuradas."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    from backend import main
    import importlib
    importlib.reload(main)
    return TestClient(main.app)


class TestHealthEndpoint:
    """Testes para GET /health."""

    def test_returns_200(self, client):
        """GET /health deve retornar status 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_ok_status(self, client):
        """GET /health deve retornar campo status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_returns_vault_path(self, client):
        """GET /health deve retornar o vault_path configurado."""
        response = client.get("/health")
        data = response.json()
        assert "vault_path" in data


class TestGenerateEndpoint:
    """Testes para POST /notes/generate (preview sem salvar)."""

    def test_returns_200_with_valid_text(self, client, sample_note):
        """POST /notes/generate com texto válido deve retornar HTTP 200."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note):
            response = client.post("/notes/generate", json={"text": "FastAPI é um framework."})
        assert response.status_code == 200

    def test_response_contains_note_fields(self, client, sample_note):
        """POST /notes/generate deve retornar campos da nota gerada."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note):
            response = client.post("/notes/generate", json={"text": "Conteúdo."})
        data = response.json()
        assert "titulo" in data
        assert "resumo" in data
        assert "tags" in data
        assert "flashcards" in data
        assert "markdown_content" in data

    def test_response_does_not_contain_file_path(self, client, sample_note):
        """POST /notes/generate NÃO deve conter file_path (nota não foi salva)."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note):
            response = client.post("/notes/generate", json={"text": "Conteúdo."})
        data = response.json()
        assert "file_path" not in data

    def test_returns_422_when_no_fields_provided(self, client):
        """POST /notes/generate sem text nem url deve retornar HTTP 422."""
        response = client.post("/notes/generate", json={})
        assert response.status_code == 422

    def test_returns_422_for_unreachable_url(self, client):
        """POST /notes/generate com URL inacessível deve retornar HTTP 422."""
        import httpx

        async def mock_failing(request):
            raise httpx.HTTPStatusError(
                "Not Found", request=None, response=type("R", (), {"status_code": 404})()
            )

        with patch("backend.main.generate_note", new_callable=AsyncMock, side_effect=mock_failing):
            response = client.post("/notes/generate", json={"url": "https://nao-existe.example"})
        assert response.status_code == 422

    def test_returns_502_on_groq_api_error(self, client):
        """POST /notes/generate deve retornar HTTP 502 quando o Groq falha."""
        import groq as groq_sdk

        async def mock_api_error(request):
            raise groq_sdk.APIConnectionError(request=None)

        with patch("backend.main.generate_note", new_callable=AsyncMock, side_effect=mock_api_error):
            response = client.post("/notes/generate", json={"text": "Conteúdo."})
        assert response.status_code == 502


class TestSaveEndpoint:
    """Testes para POST /notes/save (salvar nota previamente gerada)."""

    def test_returns_201_on_successful_save(self, client, sample_note, tmp_path, monkeypatch):
        """POST /notes/save deve retornar HTTP 201 quando a nota é salva."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path)

        payload = sample_note.model_dump()
        with patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes/save", json=payload)
        assert response.status_code == 201

    def test_response_contains_file_path(self, client, sample_note, tmp_path, monkeypatch):
        """POST /notes/save deve retornar file_path do arquivo criado."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path)

        payload = sample_note.model_dump()
        with patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes/save", json=payload)
        data = response.json()
        assert "file_path" in data
        assert data["file_path"].endswith(".md")

    def test_returns_422_with_missing_fields(self, client):
        """POST /notes/save com campos obrigatórios ausentes deve retornar 422."""
        response = client.post("/notes/save", json={"titulo": "Só título"})
        assert response.status_code == 422


class TestCreateNoteEndpoint:
    """Testes para POST /notes (gerar + salvar em um passo — retrocompatibilidade)."""

    def test_returns_201_with_valid_text(self, client, sample_note, tmp_path):
        """POST /notes com texto válido deve retornar HTTP 201."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"text": "FastAPI é um framework Python."})
        assert response.status_code == 201

    def test_response_contains_all_fields(self, client, sample_note, tmp_path):
        """POST /notes deve retornar todos os campos incluindo file_path."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"text": "Conteúdo."})
        data = response.json()
        assert "titulo" in data
        assert "file_path" in data
        assert "markdown_content" in data

    def test_accepts_url_input(self, client, sample_note, tmp_path):
        """POST /notes deve aceitar input com campo url."""
        sample_note.fonte = "https://fastapi.tiangolo.com"
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"url": "https://fastapi.tiangolo.com"})
        assert response.status_code == 201
        assert response.json()["fonte"] == "https://fastapi.tiangolo.com"


class TestExportAnkiEndpoint:
    """Testes para POST /notes/export-anki (download de arquivo para Anki)."""

    def test_returns_200_with_valid_flashcards(self, client):
        """POST /notes/export-anki com flashcards válidos retorna HTTP 200."""
        payload = {
            "flashcards": [
                {"question": "Q?", "answer": "A."},
            ],
        }
        response = client.post("/notes/export-anki", json=payload)
        assert response.status_code == 200

    def test_returns_text_file_content_type(self, client):
        """Resposta deve ter content-type de arquivo texto."""
        payload = {
            "flashcards": [{"question": "Q?", "answer": "A."}],
        }
        response = client.post("/notes/export-anki", json=payload)
        assert "text/plain" in response.headers["content-type"] or \
               "text/tab-separated-values" in response.headers["content-type"]

    def test_response_has_download_header(self, client):
        """Resposta deve conter header Content-Disposition para download."""
        payload = {
            "flashcards": [{"question": "Q?", "answer": "A."}],
            "deck": "Meu Deck",
        }
        response = client.post("/notes/export-anki", json=payload)
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert ".txt" in response.headers["content-disposition"]

    def test_filename_includes_deck_name(self, client):
        """Nome do arquivo deve incluir o nome do deck slugificado."""
        payload = {
            "flashcards": [{"question": "Q?", "answer": "A."}],
            "deck": "Second Brain",
        }
        response = client.post("/notes/export-anki", json=payload)
        assert "second-brain" in response.headers["content-disposition"]

    def test_body_contains_flashcard_data(self, client):
        """Corpo da resposta contém os dados dos flashcards."""
        payload = {
            "flashcards": [
                {"question": "O que é Python?", "answer": "Uma linguagem."},
                {"question": "O que é FastAPI?", "answer": "Um framework."},
            ],
            "tags": ["python"],
        }
        response = client.post("/notes/export-anki", json=payload)
        body = response.text
        assert "O que é Python?" in body
        assert "Uma linguagem." in body
        assert "python" in body

    def test_returns_422_with_empty_flashcards(self, client):
        """POST /notes/export-anki com flashcards vazio retorna 422."""
        payload = {"flashcards": []}
        response = client.post("/notes/export-anki", json=payload)
        assert response.status_code == 422

    def test_accepts_custom_separator(self, client):
        """Aceita separador customizado (ponto-e-vírgula)."""
        payload = {
            "flashcards": [{"question": "Q?", "answer": "A."}],
            "separator": ";",
        }
        response = client.post("/notes/export-anki", json=payload)
        assert ";" in response.text
