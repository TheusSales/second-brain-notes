"""Testes para o módulo note_generator.py.

Verifica a validação dos modelos Pydantic, o parsing da resposta JSON do Claude
e o comportamento de fetch de URLs. Todas as chamadas à API externa são mockadas.
"""

import json

import pytest
from pydantic import ValidationError


class TestNoteRequest:
    """Testes para o modelo NoteRequest."""

    def test_accepts_text_only(self):
        """NoteRequest deve aceitar somente o campo text."""
        from backend.note_generator import NoteRequest
        req = NoteRequest(text="Algum conteúdo de texto.")
        assert req.text == "Algum conteúdo de texto."
        assert req.url is None

    def test_accepts_url_only(self):
        """NoteRequest deve aceitar somente o campo url."""
        from backend.note_generator import NoteRequest
        req = NoteRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.text is None

    def test_accepts_both_fields(self):
        """NoteRequest deve aceitar text e url simultaneamente."""
        from backend.note_generator import NoteRequest
        req = NoteRequest(text="Conteúdo", url="https://example.com")
        assert req.text == "Conteúdo"
        assert req.url == "https://example.com"

    def test_rejects_empty_request(self):
        """NoteRequest deve rejeitar quando nem text nem url são fornecidos."""
        from backend.note_generator import NoteRequest
        with pytest.raises(ValidationError) as exc_info:
            NoteRequest()
        assert "text" in str(exc_info.value) or "url" in str(exc_info.value)


class TestFlashcard:
    """Testes para o modelo Flashcard."""

    def test_valid_flashcard(self):
        """Flashcard deve aceitar question e answer válidos."""
        from backend.note_generator import Flashcard
        fc = Flashcard(question="O que é Python?", answer="Uma linguagem de programação.")
        assert fc.question == "O que é Python?"
        assert fc.answer == "Uma linguagem de programação."

    def test_missing_question_raises(self):
        """Flashcard deve rejeitar se question estiver ausente."""
        from backend.note_generator import Flashcard
        with pytest.raises(ValidationError):
            Flashcard(answer="Uma resposta.")

    def test_missing_answer_raises(self):
        """Flashcard deve rejeitar se answer estiver ausente."""
        from backend.note_generator import Flashcard
        with pytest.raises(ValidationError):
            Flashcard(question="Uma pergunta?")


class TestGeneratedNote:
    """Testes para o modelo GeneratedNote."""

    def test_valid_generated_note(self):
        """GeneratedNote deve aceitar todos os campos obrigatórios."""
        from backend.note_generator import Flashcard, GeneratedNote
        note = GeneratedNote(
            titulo="Teste",
            resumo="Um resumo.",
            flashcards=[Flashcard(question="Q?", answer="A.")],
            tags=["python"],
            fonte="manual",
            date="2026-03-26",
            body="Conteúdo da nota.",
        )
        assert note.titulo == "Teste"
        assert len(note.flashcards) == 1
        assert note.tags == ["python"]

    def test_empty_flashcards_allowed(self):
        """GeneratedNote deve aceitar lista vazia de flashcards."""
        from backend.note_generator import GeneratedNote
        note = GeneratedNote(
            titulo="Teste",
            resumo="Um resumo.",
            flashcards=[],
            tags=["python"],
            fonte="manual",
            date="2026-03-26",
            body="Conteúdo.",
        )
        assert note.flashcards == []


class TestParseLlmResponse:
    """Testes para a função de parsing da resposta do Claude."""

    def test_parses_valid_json(self):
        """parse_llm_response deve converter JSON válido em GeneratedNote."""
        from backend.note_generator import parse_llm_response
        raw = json.dumps({
            "titulo": "FastAPI",
            "resumo": "Framework Python.",
            "flashcards": [{"question": "O que é?", "answer": "Um framework."}],
            "tags": ["python", "api"],
            "body": "## FastAPI\nConteúdo aqui.",
        })
        note = parse_llm_response(raw, fonte="manual", date="2026-03-26")
        assert note.titulo == "FastAPI"
        assert len(note.flashcards) == 1
        assert note.fonte == "manual"
        assert note.date == "2026-03-26"

    def test_strips_markdown_fences(self):
        """parse_llm_response deve remover markdown fences se presentes."""
        from backend.note_generator import parse_llm_response
        raw = "```json\n" + json.dumps({
            "titulo": "Teste",
            "resumo": "Resumo.",
            "flashcards": [],
            "tags": ["test"],
            "body": "Conteúdo.",
        }) + "\n```"
        note = parse_llm_response(raw, fonte="manual", date="2026-03-26")
        assert note.titulo == "Teste"

    def test_raises_on_invalid_json(self):
        """parse_llm_response deve lançar json.JSONDecodeError para JSON inválido."""
        from backend.note_generator import parse_llm_response
        with pytest.raises(Exception):
            parse_llm_response("isso não é json", fonte="manual", date="2026-03-26")

    def test_raises_on_missing_required_fields(self):
        """parse_llm_response deve lançar erro se campos obrigatórios faltarem."""
        from backend.note_generator import parse_llm_response
        raw = json.dumps({"titulo": "Só título"})  # faltam campos
        with pytest.raises(Exception):
            parse_llm_response(raw, fonte="manual", date="2026-03-26")


class TestGenerateNote:
    """Testes de integração para generate_note com Claude mockado."""

    @pytest.mark.asyncio
    async def test_generate_note_from_text(self, monkeypatch):
        """generate_note deve retornar GeneratedNote quando texto é fornecido."""
        from unittest.mock import MagicMock, patch
        from backend.note_generator import NoteRequest, generate_note

        fake_response_json = json.dumps({
            "titulo": "FastAPI é Incrível",
            "resumo": "FastAPI é um framework de alta performance.",
            "flashcards": [{"question": "O que é FastAPI?", "answer": "Framework Python."}],
            "tags": ["python", "fastapi"],
            "body": "## FastAPI\nConteúdo detalhado.",
        })

        mock_response = MagicMock()
        mock_response.choices[0].message.content = fake_response_json

        with patch("backend.note_generator.groq_sdk.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            request = NoteRequest(text="FastAPI é um framework Python.")
            note = await generate_note(request)

        assert note.titulo == "FastAPI é Incrível"
        assert note.fonte == "manual"
        assert len(note.flashcards) == 1

    @pytest.mark.asyncio
    async def test_generate_note_from_url(self, monkeypatch):
        """generate_note deve fazer fetch da URL e retornar GeneratedNote."""
        from unittest.mock import MagicMock, patch, AsyncMock
        from backend.note_generator import NoteRequest, generate_note
        import backend.note_generator as ng

        fake_response_json = json.dumps({
            "titulo": "Artigo Incrível",
            "resumo": "Resumo do artigo.",
            "flashcards": [],
            "tags": ["artigo"],
            "body": "## Artigo\nConteúdo.",
        })

        mock_response = MagicMock()
        mock_response.choices[0].message.content = fake_response_json

        with patch("backend.note_generator.groq_sdk.Groq") as MockGroq, \
             patch.object(ng, "fetch_url_content", new=AsyncMock(return_value="Conteúdo extraído.")):
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            request = NoteRequest(url="https://example.com/artigo")
            note = await generate_note(request)

        assert note.titulo == "Artigo Incrível"
        assert note.fonte == "https://example.com/artigo"
