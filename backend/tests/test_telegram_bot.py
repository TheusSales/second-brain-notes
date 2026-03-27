"""Testes para o bot do Telegram.

Testa os handlers de mensagem do bot: /start, texto livre, URLs,
preview com confirmação, callbacks de salvar/descartar e exportação Anki.

Example:
    pytest backend/tests/test_telegram_bot.py -v
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.note_generator import Flashcard, GeneratedNote


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_note():
    """Nota de exemplo retornada pelo mock do generate_note."""
    return GeneratedNote(
        titulo="FastAPI Fundamentos",
        resumo="FastAPI é um framework moderno para construção de APIs.",
        flashcards=[
            Flashcard(question="O que é FastAPI?", answer="Framework Python para APIs."),
            Flashcard(question="Qual a vantagem?", answer="Alta performance."),
        ],
        tags=["python", "fastapi"],
        fonte="manual",
        date="2026-03-27",
        body="## FastAPI\n\nFramework moderno para APIs.",
        connections=[],
    )


@pytest.fixture
def mock_update():
    """Mock do objeto Update do Telegram."""
    update = MagicMock()
    update.effective_user.first_name = "Matheus"
    update.message = AsyncMock()
    update.message.text = ""
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    return update


@pytest.fixture
def mock_callback_query():
    """Mock do objeto CallbackQuery para testes de botões inline."""
    query = AsyncMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_document = AsyncMock()
    return query


@pytest.fixture
def mock_context():
    """Mock do objeto Context do Telegram."""
    context = MagicMock()
    context.user_data = {}
    return context


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

class TestStartHandler:
    """Testes para o comando /start."""

    async def test_replies_with_welcome_message(self, mock_update, mock_context):
        """O comando /start deve enviar mensagem de boas-vindas."""
        from backend.telegram_bot import start_handler

        await start_handler(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Matheus" in text

    async def test_welcome_mentions_instructions(self, mock_update, mock_context):
        """A mensagem de boas-vindas deve conter instruções de uso."""
        from backend.telegram_bot import start_handler

        await start_handler(mock_update, mock_context)
        text = mock_update.message.reply_text.call_args[0][0]
        assert "texto" in text.lower() or "url" in text.lower()


# ---------------------------------------------------------------------------
# Mensagem de texto → gerar preview (sem salvar)
# ---------------------------------------------------------------------------

class TestMessageHandler:
    """Testes para mensagens de texto (geração de preview)."""

    async def test_replies_with_processing_message(self, mock_update, mock_context, sample_note):
        """Deve enviar mensagem de processamento antes de gerar."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "FastAPI é um framework Python."

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, return_value=sample_note):
            await message_handler(mock_update, mock_context)

        calls = mock_update.message.reply_text.call_args_list
        first_call_text = calls[0][0][0]
        assert "gerando" in first_call_text.lower() or "processando" in first_call_text.lower()

    async def test_generates_without_saving(self, mock_update, mock_context, sample_note):
        """Deve gerar a nota mas NÃO salvar automaticamente."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "FastAPI é um framework Python."

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, return_value=sample_note) as mock_gen, \
             patch("backend.telegram_bot.save_note") as mock_save:
            await message_handler(mock_update, mock_context)

        mock_gen.assert_called_once()
        mock_save.assert_not_called()

    async def test_replies_with_preview_and_buttons(self, mock_update, mock_context, sample_note):
        """Deve responder com preview da nota e botões inline."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "FastAPI é um framework Python."

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, return_value=sample_note):
            await message_handler(mock_update, mock_context)

        calls = mock_update.message.reply_text.call_args_list
        last_call = calls[-1]
        text = last_call[0][0]
        assert "FastAPI Fundamentos" in text
        # Deve ter reply_markup com botões
        assert "reply_markup" in last_call[1]

    async def test_stores_note_in_user_data(self, mock_update, mock_context, sample_note):
        """Deve armazenar a nota no user_data para confirmação posterior."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "FastAPI é um framework Python."

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, return_value=sample_note):
            await message_handler(mock_update, mock_context)

        assert "last_note" in mock_context.user_data
        assert mock_context.user_data["last_note"].titulo == "FastAPI Fundamentos"

    async def test_detects_url_in_message(self, mock_update, mock_context, sample_note):
        """Deve detectar URL e enviar como campo url no request."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "https://fastapi.tiangolo.com"

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, return_value=sample_note) as mock_gen:
            await message_handler(mock_update, mock_context)

        request = mock_gen.call_args[0][0]
        assert request.url == "https://fastapi.tiangolo.com"

    async def test_handles_generation_error(self, mock_update, mock_context):
        """Deve responder com mensagem de erro se a geração falhar."""
        from backend.telegram_bot import message_handler

        mock_update.message.text = "Conteúdo qualquer."

        with patch("backend.telegram_bot.generate_note", new_callable=AsyncMock, side_effect=Exception("LLM error")):
            await message_handler(mock_update, mock_context)

        calls = mock_update.message.reply_text.call_args_list
        last_text = calls[-1][0][0]
        assert "erro" in last_text.lower()


# ---------------------------------------------------------------------------
# Callbacks — Salvar / Descartar / Anki
# ---------------------------------------------------------------------------

class TestSaveCallback:
    """Testes para o callback de salvar nota."""

    async def test_saves_note_on_confirm(self, mock_callback_query, mock_context, sample_note):
        """Deve salvar a nota quando o usuário confirma."""
        from backend.telegram_bot import save_callback

        mock_context.user_data["last_note"] = sample_note
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        with patch("backend.telegram_bot.save_note", return_value=Path("/tmp/nota.md")) as mock_save:
            await save_callback(mock_update, mock_context)

        mock_save.assert_called_once_with(sample_note)

    async def test_replies_with_success(self, mock_callback_query, mock_context, sample_note):
        """Deve editar a mensagem com confirmação de sucesso."""
        from backend.telegram_bot import save_callback

        mock_context.user_data["last_note"] = sample_note
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        with patch("backend.telegram_bot.save_note", return_value=Path("/tmp/nota.md")):
            await save_callback(mock_update, mock_context)

        mock_callback_query.edit_message_text.assert_called_once()
        text = mock_callback_query.edit_message_text.call_args[0][0]
        assert "salva" in text.lower()

    async def test_handles_no_note(self, mock_callback_query, mock_context):
        """Deve responder com erro se não houver nota pendente."""
        from backend.telegram_bot import save_callback

        mock_context.user_data.clear()
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        await save_callback(mock_update, mock_context)
        mock_callback_query.edit_message_text.assert_called_once()
        text = mock_callback_query.edit_message_text.call_args[0][0]
        assert "nenhuma nota" in text.lower() or "expirou" in text.lower()


class TestDiscardCallback:
    """Testes para o callback de descartar nota."""

    async def test_clears_note_from_user_data(self, mock_callback_query, mock_context, sample_note):
        """Deve remover a nota do user_data."""
        from backend.telegram_bot import discard_callback

        mock_context.user_data["last_note"] = sample_note
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        await discard_callback(mock_update, mock_context)
        assert "last_note" not in mock_context.user_data

    async def test_replies_with_discard_message(self, mock_callback_query, mock_context, sample_note):
        """Deve editar a mensagem confirmando o descarte."""
        from backend.telegram_bot import discard_callback

        mock_context.user_data["last_note"] = sample_note
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        await discard_callback(mock_update, mock_context)
        mock_callback_query.edit_message_text.assert_called_once()
        text = mock_callback_query.edit_message_text.call_args[0][0]
        assert "descartada" in text.lower()


# ---------------------------------------------------------------------------
# /anki e callback anki
# ---------------------------------------------------------------------------

class TestAnkiHandler:
    """Testes para exportação de flashcards para Anki."""

    async def test_exports_flashcards_file(self, mock_update, mock_context, sample_note):
        """O comando /anki deve enviar um arquivo com os flashcards."""
        from backend.telegram_bot import anki_handler

        mock_context.user_data["last_note"] = sample_note

        await anki_handler(mock_update, mock_context)
        mock_update.message.reply_document.assert_called_once()

    async def test_file_contains_flashcard_data(self, mock_update, mock_context, sample_note):
        """O arquivo enviado deve conter as perguntas e respostas."""
        from backend.telegram_bot import anki_handler

        mock_context.user_data["last_note"] = sample_note

        await anki_handler(mock_update, mock_context)

        sent_file = mock_update.message.reply_document.call_args[1]["document"]
        content = sent_file.read().decode("utf-8")
        assert "O que é FastAPI?" in content
        assert "Framework Python para APIs." in content

    async def test_replies_error_when_no_note(self, mock_update, mock_context):
        """Deve responder com erro se não houver nota gerada."""
        from backend.telegram_bot import anki_handler

        mock_context.user_data.clear()

        await anki_handler(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "nenhuma nota" in text.lower() or "gere uma nota" in text.lower()

    async def test_anki_callback_sends_file(self, mock_callback_query, mock_context, sample_note):
        """O callback anki_inline deve enviar arquivo via reply_document."""
        from backend.telegram_bot import anki_callback

        mock_context.user_data["last_note"] = sample_note
        mock_update = MagicMock()
        mock_update.callback_query = mock_callback_query

        await anki_callback(mock_update, mock_context)
        mock_callback_query.message.reply_document.assert_called_once()
