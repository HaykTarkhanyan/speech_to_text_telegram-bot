"""
Armenian Speech-to-Text Telegram Bot
Uses Google Gemini for transcription.
"""

import json
import logging
import os
import tempfile

import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ADMIN_USER_ID = int(os.environ["ADMIN_USER_ID"])

WHITELIST_FILE = "whitelist.json"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ---------------------------------------------------------------------------
# Whitelist helpers
# ---------------------------------------------------------------------------

def load_whitelist() -> set[int]:
    """Load whitelisted user IDs from disk."""
    if not os.path.exists(WHITELIST_FILE):
        return set()
    with open(WHITELIST_FILE, "r") as f:
        return set(json.load(f))


def save_whitelist(whitelist: set[int]) -> None:
    """Persist whitelisted user IDs to disk."""
    with open(WHITELIST_FILE, "w") as f:
        json.dump(list(whitelist), f)


def is_allowed(user_id: int) -> bool:
    """Return True if the user is the admin or in the whitelist."""
    if user_id == ADMIN_USER_ID:
        return True
    return user_id in load_whitelist()


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ You are not authorised to use this bot.")
        return
    await update.message.reply_text(
        "👋 Send me a voice message or audio file in Armenian and I'll transcribe it for you."
    )


async def whitelist_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: add a user to the whitelist. Usage: /whitelist_add <user_id>"""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ This command is for the admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /whitelist_add <user_id>")
        return
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID — must be a number.")
        return
    whitelist = load_whitelist()
    whitelist.add(new_id)
    save_whitelist(whitelist)
    await update.message.reply_text(f"✅ User {new_id} added to the whitelist.")


async def whitelist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: remove a user from the whitelist. Usage: /whitelist_remove <user_id>"""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ This command is for the admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /whitelist_remove <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID — must be a number.")
        return
    whitelist = load_whitelist()
    whitelist.discard(target_id)
    save_whitelist(whitelist)
    await update.message.reply_text(f"✅ User {target_id} removed from the whitelist.")


async def whitelist_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: list all whitelisted users."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ This command is for the admin only.")
        return
    whitelist = load_whitelist()
    if not whitelist:
        await update.message.reply_text("Whitelist is empty.")
    else:
        ids = "\n".join(str(uid) for uid in sorted(whitelist))
        await update.message.reply_text(f"Whitelisted users:\n{ids}")


# ---------------------------------------------------------------------------
# Audio transcription handler
# ---------------------------------------------------------------------------

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files, transcribe using Gemini."""
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ You are not authorised to use this bot.")
        return

    # Determine the file object (voice or audio)
    file_obj = update.message.voice or update.message.audio
    if file_obj is None:
        await update.message.reply_text("Please send a voice message or audio file.")
        return

    status_msg = await update.message.reply_text("⏳ Transcribing…")

    try:
        tg_file = await file_obj.get_file()

        # Determine MIME type
        if update.message.voice:
            mime_type = "audio/ogg"
            suffix = ".ogg"
        else:
            mime_type = file_obj.mime_type or "audio/mpeg"
            suffix = os.path.splitext(file_obj.file_name)[1] if file_obj.file_name else ".mp3"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        uploaded = None
        try:
            await tg_file.download_to_drive(tmp_path)

            # Upload to Gemini File API
            uploaded = genai.upload_file(tmp_path, mime_type=mime_type)

            prompt = (
                "Transcribe the following Armenian audio exactly as spoken. "
                "Return only the transcribed text, nothing else."
            )
            response = model.generate_content([prompt, uploaded])
            transcript = response.text.strip()

            await status_msg.edit_text(transcript if transcript else "⚠️ Could not transcribe the audio.")
        finally:
            os.unlink(tmp_path)
            if uploaded is not None:
                try:
                    uploaded.delete()
                except Exception:
                    pass

    except Exception as e:
        logger.exception("Transcription error for user %s", user_id)
        await status_msg.edit_text(f"❌ Error during transcription: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whitelist_add", whitelist_add))
    app.add_handler(CommandHandler("whitelist_remove", whitelist_remove))
    app.add_handler(CommandHandler("whitelist_list", whitelist_list))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    logger.info("Bot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
