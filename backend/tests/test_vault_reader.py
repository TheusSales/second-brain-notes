"""Testes para o módulo vault_reader.py.

Verifica a leitura de notas existentes no vault do Obsidian,
incluindo extração de título e tags tanto de notas com frontmatter
YAML quanto de notas sem frontmatter.
"""

from pathlib import Path

import pytest


@pytest.fixture
def vault(tmp_path):
    """Cria um vault temporário com notas de exemplo."""
    # Nota com frontmatter YAML completo
    (tmp_path / "nota-com-frontmatter.md").write_text(
        '---\ntitulo: "Metodologias Ágeis"\ntags:\n  - agil\n  - gestao\n---\n\n# Metodologias Ágeis\nConteúdo.',
        encoding="utf-8",
    )

    # Nota sem frontmatter (formato livre)
    (tmp_path / "nota-simples.md").write_text(
        "# Angular Basics\n\nConteúdo sobre Angular.",
        encoding="utf-8",
    )

    # Nota com frontmatter parcial (só tags, sem titulo)
    (tmp_path / "nota-parcial.md").write_text(
        "---\ntags:\n  - python\n---\n\n# FastAPI\nConteúdo.",
        encoding="utf-8",
    )

    # Nota em subpasta
    subdir = tmp_path / "Principais notas"
    subdir.mkdir()
    (subdir / "DTO.md").write_text(
        "[[arquitetura de software]]\nData Transfer Object.",
        encoding="utf-8",
    )

    # Arquivo não-markdown (deve ser ignorado)
    (tmp_path / "imagem.png").write_bytes(b"\x89PNG")

    # Pasta Templates (deve ser ignorada)
    templates = tmp_path / "Templates"
    templates.mkdir()
    (templates / "template.md").write_text("---\ntemplate: true\n---\nTemplate.", encoding="utf-8")

    return tmp_path


class TestGetVaultNotes:
    """Testes para a função get_vault_notes."""

    def test_returns_list(self, vault, monkeypatch):
        """get_vault_notes deve retornar uma lista."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        assert isinstance(result, list)

    def test_finds_all_markdown_files(self, vault, monkeypatch):
        """Deve encontrar notas .md incluindo subpastas, excluindo Templates."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        titles = [n["title"] for n in result]
        assert len(result) == 4  # 3 na raiz + 1 em subpasta, sem template

    def test_extracts_title_from_frontmatter(self, vault, monkeypatch):
        """Deve usar o campo titulo do frontmatter quando disponível."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        fm_note = next(n for n in result if "metodologias" in n["title"].lower())
        assert fm_note["title"] == "Metodologias Ágeis"

    def test_falls_back_to_filename_without_frontmatter(self, vault, monkeypatch):
        """Sem frontmatter, deve usar o nome do arquivo (sem extensão) como título."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        simple = next(n for n in result if "nota-simples" in n["title"].lower() or "angular" in n["title"].lower())
        assert simple["title"] in ("nota-simples", "Angular Basics")

    def test_extracts_tags_from_frontmatter(self, vault, monkeypatch):
        """Deve extrair as tags do frontmatter YAML."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        fm_note = next(n for n in result if "metodologias" in n["title"].lower())
        assert "agil" in fm_note["tags"]
        assert "gestao" in fm_note["tags"]

    def test_empty_tags_without_frontmatter(self, vault, monkeypatch):
        """Notas sem frontmatter devem ter lista de tags vazia."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        dto = next(n for n in result if "dto" in n["title"].lower())
        assert dto["tags"] == []

    def test_ignores_templates_folder(self, vault, monkeypatch):
        """Notas na pasta Templates devem ser ignoradas."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        titles = [n["title"].lower() for n in result]
        assert not any("template" in t for t in titles)

    def test_ignores_non_markdown_files(self, vault, monkeypatch):
        """Arquivos que não são .md devem ser ignorados."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        assert all(n["title"] != "imagem" for n in result)

    def test_returns_empty_for_nonexistent_vault(self, tmp_path, monkeypatch):
        """Deve retornar lista vazia se o vault não existir."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path / "nao-existe")
        from backend.vault_reader import get_vault_notes

        result = get_vault_notes()
        assert result == []


class TestFormatVaultContext:
    """Testes para a função format_vault_context."""

    def test_formats_notes_as_string(self, vault, monkeypatch):
        """Deve formatar as notas em uma string legível para o prompt."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", vault)
        from backend.vault_reader import format_vault_context

        context = format_vault_context()
        assert "Metodologias Ágeis" in context

    def test_returns_empty_message_when_no_notes(self, tmp_path, monkeypatch):
        """Deve retornar string vazia quando não há notas no vault."""
        from backend import config
        monkeypatch.setattr(config.settings, "obsidian_vault_path", tmp_path / "nao-existe")
        from backend.vault_reader import format_vault_context

        context = format_vault_context()
        assert context == ""
