"""Módulo responsável por salvar notas geradas no vault do Obsidian.

Converte um objeto GeneratedNote em um arquivo .md com frontmatter YAML
e salva na pasta Inbox configurada. Também expõe funções auxiliares para
geração de nome de arquivo e renderização do conteúdo.

Example:
    >>> from backend.note_generator import GeneratedNote, Flashcard
    >>> from backend.obsidian_writer import save_note
    >>> note = GeneratedNote(titulo="Minha Nota", ...)
    >>> path = save_note(note)
    >>> print(path)
    /home/user/Documents/Obsidian/Vault/Inbox/2026-03-26-minha-nota.md
"""

from pathlib import Path

from slugify import slugify

from backend.config import settings
from backend.note_generator import GeneratedNote


def build_filename(titulo: str, date: str) -> str:
    """Gera o nome do arquivo .md a partir do título e data.

    Converte o título para um slug ASCII seguro para uso como nome de arquivo,
    com a data como prefixo no formato ISO.

    Args:
        titulo: Título da nota (pode conter acentos e caracteres especiais).
        date: Data no formato ISO (YYYY-MM-DD).

    Returns:
        Nome do arquivo no formato 'YYYY-MM-DD-titulo-slugificado.md'.

    Example:
        >>> build_filename("Introdução ao FastAPI", "2026-03-26")
        '2026-03-26-introducao-ao-fastapi.md'
    """
    slug = slugify(titulo, max_length=60, word_boundary=True)
    return f"{date}-{slug}.md"


def render_note(note: GeneratedNote) -> str:
    """Renderiza o conteúdo completo do arquivo .md com frontmatter YAML.

    Monta o frontmatter YAML com todos os campos obrigatórios seguido do
    corpo da nota em Markdown. Aspas duplas em campos de texto são escapadas
    para não quebrar o YAML.

    Args:
        note: Objeto GeneratedNote com todos os campos preenchidos.

    Returns:
        String com o conteúdo completo do arquivo .md pronto para escrita.
    """
    def escape(text: str) -> str:
        """Escapa aspas duplas para uso seguro em campos YAML entre aspas."""
        return text.replace('"', "'")

    tags_yaml = "\n".join(f"  - {tag}" for tag in note.tags)

    flashcards_yaml = "\n".join(
        f'  - q: "{escape(fc.question)}"\n    a: "{escape(fc.answer)}"'
        for fc in note.flashcards
    )

    frontmatter_lines = [
        "---",
        f'titulo: "{escape(note.titulo)}"',
        f'resumo: "{escape(note.resumo)}"',
        "tags:",
        tags_yaml,
    ]

    if note.flashcards:
        frontmatter_lines.extend(["flashcards:", flashcards_yaml])
    else:
        frontmatter_lines.append("flashcards: []")

    if note.connections:
        connections_yaml = "\n".join(f"  - \"[[{escape(c)}]]\"" for c in note.connections)
        frontmatter_lines.extend(["connections:", connections_yaml])
    else:
        frontmatter_lines.append("connections: []")

    frontmatter_lines.extend([
        f'fonte: "{escape(note.fonte)}"',
        f"date: {note.date}",
        "---",
    ])

    frontmatter = "\n".join(frontmatter_lines)
    return f"{frontmatter}\n\n# {note.titulo}\n\n{note.body}\n"


def save_note(note: GeneratedNote) -> Path:
    """Salva a nota gerada como arquivo .md no vault do Obsidian.

    Cria a pasta do vault se ela não existir. Se um arquivo com o mesmo nome
    já existir (mesma data e título), adiciona um sufixo numérico para evitar
    sobrescrita silenciosa.

    Args:
        note: Objeto GeneratedNote com todos os campos preenchidos.

    Returns:
        Path completo do arquivo .md criado.

    Raises:
        OSError: Se não for possível criar o diretório ou escrever o arquivo.
    """
    vault_path = settings.obsidian_vault_path
    vault_path.mkdir(parents=True, exist_ok=True)

    filename = build_filename(note.titulo, note.date)
    file_path = vault_path / filename

    counter = 1
    while file_path.exists():
        base = filename.replace(".md", "")
        file_path = vault_path / f"{base}-{counter}.md"
        counter += 1

    content = render_note(note)
    file_path.write_text(content, encoding="utf-8")

    return file_path
