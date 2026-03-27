"""Bot do Telegram para o Second Brain Notes.

Permite gerar e salvar notas de aprendizado diretamente pelo Telegram.
O usuário envia texto ou URL, recebe um preview da nota e confirma
se deseja salvar no Obsidian. O comando /anki exporta os flashcards.

Fluxo:
    1. Usuário envia texto ou URL
    2. Bot gera preview com título, resumo, tags e flashcards
    3. Botões inline: Salvar | Exportar Anki | Descartar
    4. Usuário confirma a ação desejada

Handlers:
    /start — Mensagem de boas-vindas com instruções.
    mensagem de texto — Gera preview da nota (sem salvar).
    /anki — Exporta flashcards da última nota como arquivo para Anki.

Callbacks:
    save — Salva a nota no vault do Obsidian.
    discard — Descarta a nota gerada.
    anki — Exporta flashcards como arquivo.

Example:
    Rodando o bot standalone::

        python -m backend.telegram_bot
"""

import io
import re

from backend.anki_exporter import AnkiExportRequest, export_csv
from backend.note_generator import NoteRequest, generate_note
from backend.obsidian_writer import save_note


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(r"https?://\S+")


def _is_url(text: str) -> bool:
    """Verifica se o texto é uma URL.

    Args:
        text: Texto a ser verificado.

    Returns:
        True se o texto começa com http:// ou https://.
    """
    return bool(_URL_PATTERN.match(text.strip()))


def _format_preview(note) -> str:
    """Formata o preview da nota para envio no Telegram.

    Args:
        note: Objeto GeneratedNote com os dados da nota.

    Returns:
        String formatada com título, resumo, tags e flashcards.
    """
    tags_str = ", ".join(note.tags)
    flashcards_count = len(note.flashcards)
    return (
        f"📝 *Preview da nota*\n\n"
        f"*{note.titulo}*\n"
        f"{note.resumo}\n\n"
        f"🏷 Tags: {tags_str}\n"
        f"🃏 Flashcards: {flashcards_count}\n\n"
        f"Deseja salvar no Obsidian?"
    )


def _build_inline_keyboard():
    """Constrói o teclado inline com botões de ação.

    Returns:
        InlineKeyboardMarkup com botões Salvar, Anki e Descartar.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("✅ Salvar", callback_data="save"),
            InlineKeyboardButton("🃏 Anki", callback_data="anki"),
            InlineKeyboardButton("❌ Descartar", callback_data="discard"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def _send_anki_file(note):
    """Cria o buffer do arquivo Anki para envio.

    Args:
        note: Objeto GeneratedNote com flashcards.

    Returns:
        Tupla (file_buf, caption) pronta para reply_document.
    """
    request = AnkiExportRequest(
        flashcards=note.flashcards,
        deck=note.titulo,
        tags=note.tags,
    )
    content = export_csv(request)

    file_buf = io.BytesIO(content.encode("utf-8"))
    file_buf.name = f"anki-{note.date}.txt"
    caption = f"🃏 {len(note.flashcards)} flashcards exportados para o Anki."
    return file_buf, caption


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start_handler(update, context) -> None:
    """Handler para o comando /start.

    Envia mensagem de boas-vindas com instruções de uso.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Olá, {name}! 👋\n\n"
        f"Eu sou o bot do Second Brain Notes.\n"
        f"Envie um texto ou URL e eu vou gerar um preview da nota.\n"
        f"Você poderá revisar antes de salvar no Obsidian.\n\n"
        f"Comandos:\n"
        f"/anki — Exportar flashcards da última nota para o Anki"
    )


async def message_handler(update, context) -> None:
    """Handler para mensagens de texto (gerar preview sem salvar).

    Detecta se o conteúdo é uma URL ou texto livre, gera a nota via LLM
    e responde com preview e botões de confirmação.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    text = update.message.text.strip()

    await update.message.reply_text("⏳ Gerando nota...")

    try:
        if _is_url(text):
            request = NoteRequest(url=text)
        else:
            request = NoteRequest(text=text)

        note = await generate_note(request)
        context.user_data["last_note"] = note

        preview = _format_preview(note)
        keyboard = _build_inline_keyboard()
        await update.message.reply_text(
            preview,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    except Exception as exc:
        await update.message.reply_text(
            f"❌ Erro ao gerar nota: {str(exc)}"
        )


# ---------------------------------------------------------------------------
# Callbacks (botões inline)
# ---------------------------------------------------------------------------

async def save_callback(update, context) -> None:
    """Callback para o botão 'Salvar' — salva a nota no vault.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    query = update.callback_query
    await query.answer()

    note = context.user_data.get("last_note")
    if not note:
        await query.edit_message_text("⚠️ Nenhuma nota pendente. A sessão expirou.")
        return

    try:
        file_path = save_note(note)
        await query.edit_message_text(
            f"✅ *Nota salva!*\n\n"
            f"*{note.titulo}*\n"
            f"📁 `{file_path}`\n\n"
            f"Use /anki para exportar os flashcards.",
            parse_mode="Markdown",
        )
    except Exception as exc:
        await query.edit_message_text(f"❌ Erro ao salvar: {str(exc)}")


async def discard_callback(update, context) -> None:
    """Callback para o botão 'Descartar' — descarta a nota gerada.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    query = update.callback_query
    await query.answer()

    context.user_data.pop("last_note", None)
    await query.edit_message_text("🗑 Nota descartada. Envie outro conteúdo quando quiser.")


async def anki_callback(update, context) -> None:
    """Callback para o botão 'Anki' — exporta flashcards como arquivo.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    query = update.callback_query
    await query.answer()

    note = context.user_data.get("last_note")
    if not note:
        await query.edit_message_text("⚠️ Nenhuma nota pendente. A sessão expirou.")
        return

    file_buf, caption = _send_anki_file(note)
    await query.message.reply_document(document=file_buf, caption=caption)


async def anki_handler(update, context) -> None:
    """Handler para o comando /anki (exportar flashcards).

    Exporta os flashcards da última nota gerada como arquivo texto
    compatível com o importador do Anki.

    Args:
        update: Objeto Update do Telegram.
        context: Objeto Context do Telegram.
    """
    note = context.user_data.get("last_note")

    if not note:
        await update.message.reply_text(
            "Nenhuma nota gerada ainda. Envie um texto ou URL primeiro."
        )
        return

    file_buf, caption = _send_anki_file(note)
    await update.message.reply_document(document=file_buf, caption=caption)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main() -> None:
    """Inicia o bot do Telegram em modo polling.

    Lê o token de ``settings.telegram_bot_token`` e registra os handlers.

    Raises:
        ValueError: Se o token não estiver configurado.
    """
    from telegram.ext import (
        ApplicationBuilder,
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    from backend.config import settings

    if not settings.telegram_bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN não configurado. "
            "Adicione ao .env: TELEGRAM_BOT_TOKEN=seu-token"
        )

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("anki", anki_handler))
    app.add_handler(CallbackQueryHandler(save_callback, pattern="^save$"))
    app.add_handler(CallbackQueryHandler(discard_callback, pattern="^discard$"))
    app.add_handler(CallbackQueryHandler(anki_callback, pattern="^anki$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 Bot do Telegram iniciado. Ctrl+C para parar.")
    app.run_polling()


if __name__ == "__main__":
    main()
