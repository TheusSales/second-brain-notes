"""Módulo de exportação de flashcards para o Anki.

Gera arquivos no formato texto (CSV/TSV) compatíveis com o importador
nativo do Anki. Cada linha contém Front (pergunta) e Back (resposta),
opcionalmente seguidos de tags.

Formato Anki de importação:
    - Separador configurável (tab padrão, ou ponto-e-vírgula)
    - Tags separadas por espaço na última coluna
    - Encoding UTF-8

Example:
    >>> from backend.anki_exporter import AnkiExportRequest, export_csv
    >>> from backend.note_generator import Flashcard
    >>> flashcards = [Flashcard(question="Q?", answer="A.")]
    >>> req = AnkiExportRequest(flashcards=flashcards, deck="Meu Deck", tags=["python"])
    >>> content = export_csv(req)
    >>> print(content)
    Q?\tA.\tpython
"""

from pydantic import BaseModel, field_validator

from backend.note_generator import Flashcard


class AnkiExportRequest(BaseModel):
    """Modelo de requisição para exportação de flashcards no formato Anki.

    Attributes:
        flashcards: Lista de flashcards (pelo menos um obrigatório).
        deck: Nome do deck no Anki (usado como metadado, não aparece no CSV).
        tags: Tags a serem aplicadas a todos os cards importados.
        separator: Caractere separador de colunas (tab ou ponto-e-vírgula).
    """

    flashcards: list[Flashcard]
    deck: str = "Default"
    tags: list[str] = []
    separator: str = "\t"

    @field_validator("flashcards")
    @classmethod
    def flashcards_not_empty(cls, v: list[Flashcard]) -> list[Flashcard]:
        """Valida que a lista de flashcards não está vazia."""
        if not v:
            raise ValueError("flashcards não pode ser uma lista vazia")
        return v


def export_csv(request: AnkiExportRequest) -> str:
    """Gera o conteúdo do arquivo texto para importação no Anki.

    Cada linha contém Front e Back separados pelo separador configurado.
    Se tags estiverem presentes, são adicionadas como terceira coluna
    separadas por espaço (formato nativo do Anki).

    Quebras de linha dentro de perguntas/respostas são substituídas por
    '<br>' para compatibilidade com o Anki (que renderiza HTML).

    Args:
        request: Objeto AnkiExportRequest com flashcards, tags e separador.

    Returns:
        String com o conteúdo do arquivo pronto para escrita/download.
    """
    sep = request.separator
    tags_str = " ".join(request.tags) if request.tags else ""
    lines = []

    for fc in request.flashcards:
        front = fc.question.replace("\n", "<br>")
        back = fc.answer.replace("\n", "<br>")

        if tags_str:
            lines.append(f"{front}{sep}{back}{sep}{tags_str}")
        else:
            lines.append(f"{front}{sep}{back}")

    return "\n".join(lines) + "\n"
