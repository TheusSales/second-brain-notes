"""Testes para o módulo de exportação de flashcards para o Anki.

Testa a geração de arquivos CSV/TSV compatíveis com o importador
nativo do Anki, incluindo encoding UTF-8, separadores e tags.

Example:
    pytest backend/tests/test_anki_exporter.py -v
"""

import csv
import io

import pytest

from backend.anki_exporter import export_csv, AnkiExportRequest
from backend.note_generator import Flashcard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_flashcards():
    """Lista de flashcards para testes."""
    return [
        Flashcard(question="O que é FastAPI?", answer="Um framework Python para APIs web."),
        Flashcard(question="Qual a vantagem do FastAPI?", answer="Alta performance com type hints."),
        Flashcard(question="O que são type hints?", answer="Anotações de tipo do Python 3.5+."),
    ]


@pytest.fixture
def sample_request(sample_flashcards):
    """Request de exportação com valores padrão."""
    return AnkiExportRequest(
        flashcards=sample_flashcards,
        deck="Second Brain",
        tags=["python", "fastapi"],
    )


# ---------------------------------------------------------------------------
# AnkiExportRequest
# ---------------------------------------------------------------------------

class TestAnkiExportRequest:
    """Testes do modelo AnkiExportRequest."""

    def test_valid_request(self, sample_flashcards):
        """Aceita flashcards com deck e tags."""
        req = AnkiExportRequest(
            flashcards=sample_flashcards,
            deck="Meu Deck",
            tags=["tag1"],
        )
        assert req.deck == "Meu Deck"
        assert req.tags == ["tag1"]

    def test_default_deck(self, sample_flashcards):
        """Deck padrão é 'Default'."""
        req = AnkiExportRequest(flashcards=sample_flashcards)
        assert req.deck == "Default"

    def test_default_tags_empty(self, sample_flashcards):
        """Tags padrão é lista vazia."""
        req = AnkiExportRequest(flashcards=sample_flashcards)
        assert req.tags == []

    def test_rejects_empty_flashcards(self):
        """Rejeita lista vazia de flashcards."""
        with pytest.raises(ValueError):
            AnkiExportRequest(flashcards=[])

    def test_separator_default_is_tab(self, sample_flashcards):
        """Separador padrão é tab."""
        req = AnkiExportRequest(flashcards=sample_flashcards)
        assert req.separator == "\t"

    def test_accepts_semicolon_separator(self, sample_flashcards):
        """Aceita ponto-e-vírgula como separador."""
        req = AnkiExportRequest(flashcards=sample_flashcards, separator=";")
        assert req.separator == ";"


# ---------------------------------------------------------------------------
# export_csv
# ---------------------------------------------------------------------------

class TestExportCsv:
    """Testes da função export_csv."""

    def test_returns_string(self, sample_request):
        """Retorna uma string."""
        result = export_csv(sample_request)
        assert isinstance(result, str)

    def test_contains_all_flashcards(self, sample_request):
        """Contém todas as linhas de flashcards."""
        result = export_csv(sample_request)
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_tab_separated_by_default(self, sample_request):
        """Usa tab como separador padrão."""
        result = export_csv(sample_request)
        first_line = result.strip().split("\n")[0]
        assert "\t" in first_line

    def test_front_and_back_columns(self, sample_request):
        """Cada linha tem front (question) e back (answer)."""
        result = export_csv(sample_request)
        first_line = result.strip().split("\n")[0]
        parts = first_line.split("\t")
        assert parts[0] == "O que é FastAPI?"
        assert parts[1] == "Um framework Python para APIs web."

    def test_includes_tags_column(self, sample_request):
        """Inclui coluna de tags quando tags estão presentes."""
        result = export_csv(sample_request)
        first_line = result.strip().split("\n")[0]
        parts = first_line.split("\t")
        assert len(parts) == 3
        assert "python" in parts[2]
        assert "fastapi" in parts[2]

    def test_tags_space_separated(self, sample_request):
        """Tags são separadas por espaço (formato Anki)."""
        result = export_csv(sample_request)
        first_line = result.strip().split("\n")[0]
        parts = first_line.split("\t")
        assert parts[2] == "python fastapi"

    def test_no_tags_column_when_empty(self, sample_flashcards):
        """Sem coluna de tags quando lista vazia."""
        req = AnkiExportRequest(flashcards=sample_flashcards, tags=[])
        result = export_csv(req)
        first_line = result.strip().split("\n")[0]
        parts = first_line.split("\t")
        assert len(parts) == 2

    def test_semicolon_separator(self, sample_flashcards):
        """Funciona com ponto-e-vírgula como separador."""
        req = AnkiExportRequest(
            flashcards=sample_flashcards,
            separator=";",
            tags=["test"],
        )
        result = export_csv(req)
        first_line = result.strip().split("\n")[0]
        parts = first_line.split(";")
        assert len(parts) == 3

    def test_utf8_characters_preserved(self):
        """Preserva caracteres UTF-8 (acentos, etc.)."""
        flashcards = [
            Flashcard(question="O que é programação?", answer="É a arte de criar soluções.")
        ]
        req = AnkiExportRequest(flashcards=flashcards)
        result = export_csv(req)
        assert "programação" in result
        assert "soluções" in result

    def test_newlines_in_content_escaped(self):
        """Quebras de linha no conteúdo são escapadas."""
        flashcards = [
            Flashcard(
                question="Quais os passos?",
                answer="1. Primeiro\n2. Segundo\n3. Terceiro",
            )
        ]
        req = AnkiExportRequest(flashcards=flashcards)
        result = export_csv(req)
        lines = result.strip().split("\n")
        # Deve ser apenas 1 linha (newlines escapadas)
        assert len(lines) == 1
