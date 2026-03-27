"""Testes de integração para os endpoints da API FastAPI (main.py).

Utiliza o TestClient do FastAPI/httpx para testar os endpoints sem precisar
subir um servidor real. As chamadas ao Claude e ao filesystem são mockadas.
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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
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


class TestCreateNoteEndpoint:
    """Testes para POST /notes."""

    def test_returns_201_with_valid_text(self, client, sample_note, tmp_path, monkeypatch):
        """POST /notes com texto válido deve retornar HTTP 201."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"text": "FastAPI é um framework Python."})

        assert response.status_code == 201

    def test_response_contains_required_fields(self, client, sample_note, tmp_path, monkeypatch):
        """POST /notes deve retornar todos os campos obrigatórios na resposta."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"text": "Conteúdo qualquer."})

        data = response.json()
        assert "titulo" in data
        assert "resumo" in data
        assert "tags" in data
        assert "flashcards" in data
        assert "file_path" in data
        assert "markdown_content" in data

    def test_response_titulo_matches_generated_note(self, client, sample_note, tmp_path):
        """POST /notes deve retornar o título gerado pelo Claude."""
        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"text": "Conteúdo qualquer."})

        assert response.json()["titulo"] == "FastAPI Fundamentos"

    def test_returns_422_when_no_fields_provided(self, client):
        """POST /notes sem text nem url deve retornar HTTP 422."""
        response = client.post("/notes", json={})
        assert response.status_code == 422

    def test_returns_422_for_unreachable_url(self, client, monkeypatch):
        """POST /notes com URL inacessível deve retornar HTTP 422."""
        import httpx

        async def mock_failing_generate(request):
            raise httpx.HTTPStatusError(
                "Not Found", request=None, response=type("R", (), {"status_code": 404})()
            )

        with patch("backend.main.generate_note", new_callable=AsyncMock, side_effect=mock_failing_generate):
            response = client.post("/notes", json={"url": "https://url-que-nao-existe.example"})

        assert response.status_code == 422

    def test_returns_502_on_groq_api_error(self, client):
        """POST /notes deve retornar HTTP 502 quando a API do Groq falha."""
        import groq as groq_sdk

        async def mock_api_error(request):
            raise groq_sdk.APIConnectionError(request=None)

        with patch("backend.main.generate_note", new_callable=AsyncMock, side_effect=mock_api_error):
            response = client.post("/notes", json={"text": "Conteúdo."})

        assert response.status_code == 502

    def test_accepts_url_input(self, client, sample_note, tmp_path):
        """POST /notes deve aceitar input com campo url."""
        sample_note.fonte = "https://fastapi.tiangolo.com"

        with patch("backend.main.generate_note", new_callable=AsyncMock, return_value=sample_note), \
             patch("backend.main.save_note", return_value=tmp_path / "2026-03-26-fastapi.md"):
            response = client.post("/notes", json={"url": "https://fastapi.tiangolo.com"})

        assert response.status_code == 201
        assert response.json()["fonte"] == "https://fastapi.tiangolo.com"
