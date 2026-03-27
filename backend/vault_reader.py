"""Módulo de leitura de notas existentes no vault do Obsidian.

Escaneia o vault configurado e extrai metadados (título, tags) de cada nota
.md para fornecer contexto ao LLM na hora de sugerir conexões entre notas.

Example:
    >>> from backend.vault_reader import get_vault_notes, format_vault_context
    >>> notes = get_vault_notes()
    >>> print(notes[0])
    {'title': 'Metodologias Ágeis', 'tags': ['agil', 'gestao']}
    >>> context = format_vault_context()
    >>> print(context)
    Notas existentes no vault:
    - Metodologias Ágeis [agil, gestao]
"""

import re
from pathlib import Path

from backend.config import settings

# Pastas do vault que devem ser ignoradas na leitura
IGNORED_FOLDERS = {"Templates", "templates", "5 - Templates"}


def _parse_frontmatter(content: str) -> dict:
    """Extrai campos do frontmatter YAML de uma nota.

    Faz parsing simplificado (sem dependência PyYAML) dos campos
    `titulo` e `tags` do frontmatter delimitado por `---`.

    Args:
        content: Conteúdo completo do arquivo .md.

    Returns:
        Dicionário com chaves 'titulo' (str ou None) e 'tags' (list[str]).
    """
    result = {"titulo": None, "tags": []}

    if not content.startswith("---"):
        return result

    end = content.find("\n---", 3)
    if end == -1:
        return result

    frontmatter = content[3:end]

    # Extrair titulo
    titulo_match = re.search(r'titulo:\s*"(.+?)"', frontmatter)
    if titulo_match:
        result["titulo"] = titulo_match.group(1)

    # Extrair tags (formato lista YAML: "  - tag")
    tags_section = re.search(r"tags:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter)
    if tags_section:
        result["tags"] = re.findall(r"-\s+(\S+)", tags_section.group(1))

    return result


def get_vault_notes() -> list[dict]:
    """Lê todas as notas .md do vault e retorna seus metadados.

    Percorre recursivamente o vault do Obsidian, ignorando pastas de
    templates. Para cada nota, extrai título (do frontmatter ou nome do
    arquivo) e tags (do frontmatter).

    Returns:
        Lista de dicionários com chaves 'title' (str) e 'tags' (list[str]).
        Retorna lista vazia se o vault não existir.
    """
    vault_path = settings.obsidian_vault_path

    if not vault_path.exists():
        return []

    notes = []
    for md_file in vault_path.rglob("*.md"):
        # Ignorar pastas de templates
        if any(ignored in md_file.parts for ignored in IGNORED_FOLDERS):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        meta = _parse_frontmatter(content)

        title = meta["titulo"] or md_file.stem
        tags = meta["tags"]

        notes.append({"title": title, "tags": tags})

    return notes


def format_vault_context() -> str:
    """Formata as notas do vault como string de contexto para o prompt do LLM.

    Gera uma lista legível com título e tags de cada nota existente,
    para que o LLM possa sugerir conexões relevantes.

    Returns:
        String formatada com as notas existentes, ou string vazia se
        não houver notas no vault.

    Example:
        >>> context = format_vault_context()
        >>> print(context)
        Notas existentes no vault:
        - Metodologias Ágeis [agil, gestao]
        - DTO []
    """
    notes = get_vault_notes()

    if not notes:
        return ""

    lines = ["Notas existentes no vault:"]
    for note in notes:
        tags_str = ", ".join(note["tags"]) if note["tags"] else ""
        if tags_str:
            lines.append(f"- {note['title']} [{tags_str}]")
        else:
            lines.append(f"- {note['title']}")

    return "\n".join(lines)
