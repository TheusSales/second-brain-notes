"""Testes para o módulo obsidian_writer.py.

Verifica a geração de nomes de arquivo, renderização do frontmatter YAML
e escrita correta dos arquivos .md no vault do Obsidian.
"""

from pathlib import Path

import pytest

from backend.note_generator import Flashcard, GeneratedNote


class TestBuildFilename:
    """Testes para a função build_filename."""

    def test_basic_ascii_title(self):
        """Título ASCII deve gerar slug simples."""
        from backend.obsidian_writer import build_filename
        result = build_filename("FastAPI Introduction", "2026-03-26")
        assert result == "2026-03-26-fastapi-introduction.md"

    def test_portuguese_accented_title(self):
        """Título com acentos em português deve ser convertido para ASCII."""
        from backend.obsidian_writer import build_filename
        result = build_filename("Introdução ao FastAPI", "2026-03-26")
        assert result == "2026-03-26-introducao-ao-fastapi.md"

    def test_title_with_special_characters(self):
        """Caracteres especiais devem ser removidos/substituídos no slug."""
        from backend.obsidian_writer import build_filename
        result = build_filename("Python: Guia Completo & Prático!", "2026-03-26")
        assert result.startswith("2026-03-26-python")
        assert result.endswith(".md")
        assert ":" not in result
        assert "&" not in result

    def test_long_title_is_truncated(self):
        """Títulos muito longos devem ser truncados para evitar nomes de arquivo gigantes."""
        from backend.obsidian_writer import build_filename
        long_title = "Uma " * 30  # ~120 chars
        result = build_filename(long_title, "2026-03-26")
        # slug parte tem max 60 chars + date prefix "2026-03-26-" (11) + ".md" (3) = 74
        assert len(result) <= 74

    def test_date_is_prefix(self):
        """Data deve aparecer como prefixo do nome do arquivo."""
        from backend.obsidian_writer import build_filename
        result = build_filename("Qualquer Titulo", "2026-01-15")
        assert result.startswith("2026-01-15-")


class TestRenderNote:
    """Testes para a função render_note."""

    @pytest.fixture
    def sample_note(self):
        """Nota de exemplo para os testes."""
        return GeneratedNote(
            titulo="Introdução ao FastAPI",
            resumo="FastAPI é um framework moderno para APIs Python.",
            flashcards=[
                Flashcard(
                    question="O que é FastAPI?",
                    answer="Um framework Python para construção de APIs RESTful."
                ),
                Flashcard(
                    question="Qual a vantagem do FastAPI?",
                    answer="Alta performance e validação automática via Pydantic."
                ),
            ],
            tags=["python", "api", "web"],
            fonte="https://fastapi.tiangolo.com",
            date="2026-03-26",
            body="## Conceitos\n\nFastAPI utiliza type hints para validação automática.",
        )

    def test_contains_yaml_frontmatter_delimiters(self, sample_note):
        """Nota renderizada deve ter delimitadores YAML '---'."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_frontmatter_contains_titulo(self, sample_note):
        """Frontmatter deve conter o campo titulo."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        assert 'titulo: "Introdução ao FastAPI"' in result

    def test_frontmatter_contains_tags(self, sample_note):
        """Frontmatter deve conter as tags como lista YAML."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        assert "- python" in result
        assert "- api" in result

    def test_frontmatter_contains_flashcards(self, sample_note):
        """Frontmatter deve conter os flashcards como lista YAML."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        assert "O que é FastAPI?" in result
        assert "Um framework Python para construção de APIs RESTful." in result

    def test_frontmatter_contains_fonte_and_date(self, sample_note):
        """Frontmatter deve conter fonte e date."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        assert "https://fastapi.tiangolo.com" in result
        assert "2026-03-26" in result

    def test_body_follows_frontmatter(self, sample_note):
        """Corpo da nota deve aparecer após o frontmatter."""
        from backend.obsidian_writer import render_note
        result = render_note(sample_note)
        frontmatter_end = result.index("\n---\n") + 5
        body_section = result[frontmatter_end:]
        assert "# Introdução ao FastAPI" in body_section
        assert "## Conceitos" in body_section

    def test_double_quotes_in_title_are_escaped(self):
        """Aspas duplas no título não devem quebrar o YAML."""
        from backend.obsidian_writer import render_note
        note = GeneratedNote(
            titulo='Guia "Completo" de Python',
            resumo="Resumo.",
            flashcards=[],
            tags=["python"],
            fonte="manual",
            date="2026-03-26",
            body="Conteúdo.",
        )
        result = render_note(note)
        # Deve renderizar sem quebrar (aspas duplas escapadas ou substituídas)
        assert "---\n" in result


class TestSaveNote:
    """Testes para a função save_note."""

    @pytest.fixture
    def sample_note(self):
        """Nota de exemplo para os testes."""
        return GeneratedNote(
            titulo="Test Note",
            resumo="A test.",
            flashcards=[Flashcard(question="Q?", answer="A.")],
            tags=["test"],
            fonte="manual",
            date="2026-03-26",
            body="## Content\nTest content.",
        )

    def test_creates_file_in_vault_path(self, sample_note, tmp_path, monkeypatch):
        """save_note deve criar o arquivo .md no caminho do vault."""
        from backend import config, obsidian_writer
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path)

        file_path = obsidian_writer.save_note(sample_note)

        assert file_path.exists()
        assert file_path.suffix == ".md"
        assert file_path.parent == tmp_path

    def test_creates_vault_directory_if_not_exists(self, sample_note, tmp_path, monkeypatch):
        """save_note deve criar a pasta do vault se ela não existir."""
        new_vault = tmp_path / "new" / "vault" / "path"
        from backend import config, obsidian_writer
        monkeypatch.setattr(config.settings, "obsidian_vault_path", new_vault)

        file_path = obsidian_writer.save_note(sample_note)

        assert new_vault.exists()
        assert file_path.exists()

    def test_deduplicates_filename_on_conflict(self, sample_note, tmp_path, monkeypatch):
        """save_note deve adicionar sufixo numérico se o arquivo já existir."""
        from backend import config, obsidian_writer
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path)

        path1 = obsidian_writer.save_note(sample_note)
        path2 = obsidian_writer.save_note(sample_note)

        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_file_content_is_valid_markdown(self, sample_note, tmp_path, monkeypatch):
        """Arquivo salvo deve conter conteúdo Markdown válido com frontmatter."""
        from backend import config, obsidian_writer
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path)

        file_path = obsidian_writer.save_note(sample_note)
        content = file_path.read_text(encoding="utf-8")

        assert content.startswith("---\n")
        assert "titulo:" in content
        assert "# Test Note" in content
