"""
Armenian Speech-to-Text Telegram Bot
Uses Google Gemini for transcription.
"""

import asyncio
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
MAX_AUDIO_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# In-memory whitelist cache and lock for concurrency-safe access
_whitelist: set[int] = set()
_whitelist_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Whitelist helpers
# ---------------------------------------------------------------------------

def _load_whitelist_from_disk() -> set[int]:
    """Load whitelist from disk; returns empty set on missing file or error."""
    if not os.path.exists(WHITELIST_FILE):
        return set()
    try:
        with open(WHITELIST_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "Failed to load whitelist from %s: %s. Treating as empty whitelist.",
            WHITELIST_FILE,
            e,
        )
        return set()
    if not isinstance(data, list):
        logger.warning(
            "Whitelist file %s has invalid format (expected list, got %s). "
            "Treating as empty whitelist.",
            WHITELIST_FILE,
            type(data).__name__,
        )
        return set()
    return set(data)


def _save_whitelist_to_disk(whitelist: set[int]) -> None:
    """Atomically persist whitelist to disk using a temp file + os.replace."""
    target = os.path.abspath(WHITELIST_FILE)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(list(whitelist), f)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_allowed(user_id: int) -> bool:
    """Return True if the user is the admin or in the in-memory whitelist."""
    if user_id == ADMIN_USER_ID:
        return True
    return user_id in _whitelist


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
    async with _whitelist_lock:
        _whitelist.add(new_id)
        _save_whitelist_to_disk(_whitelist)
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
    async with _whitelist_lock:
        _whitelist.discard(target_id)
        _save_whitelist_to_disk(_whitelist)
    await update.message.reply_text(f"✅ User {target_id} removed from the whitelist.")


async def whitelist_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: list all whitelisted users."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ This command is for the admin only.")
        return
    async with _whitelist_lock:
        snapshot = set(_whitelist)
    if not snapshot:
        await update.message.reply_text("Whitelist is empty.")
    else:
        ids = "\n".join(str(uid) for uid in sorted(snapshot))
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

    # Guard against excessively large files before downloading
    if file_obj.file_size and file_obj.file_size > MAX_AUDIO_SIZE_BYTES:
        await update.message.reply_text(
            f"⚠️ File is too large ({file_obj.file_size // (1024 * 1024)} MB). "
            f"Maximum allowed size is {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)} MB."
        )
        return

    status_msg = await update.message.reply_text("⏳ Transcribing…")

    try:
        tg_file = await file_obj.get_file()

        # Determine MIME type and file extension
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

            # Upload to Gemini File API (blocking I/O — run in thread)
            uploaded = await asyncio.to_thread(
                genai.upload_file, tmp_path, mime_type=mime_type
            )

            prompt = (
                "Transcribe the following Armenian audio exactly as spoken. "
                "Return only the transcribed text, nothing else."
            )
            # generate_content is a blocking call — run in thread
            response = await asyncio.to_thread(
                model.generate_content, [prompt, uploaded]
            )
            transcript = response.text.strip()

            await status_msg.edit_text(
                transcript if transcript else "⚠️ Could not transcribe the audio."
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning("Could not delete temp file %s: %s", tmp_path, e)
            if uploaded is not None:
                try:
                    await asyncio.to_thread(uploaded.delete)
                except Exception:
                    pass

    except Exception:
        logger.exception("Transcription error for user %s", user_id)
        await status_msg.edit_text("❌ Error during transcription. Please try again later.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _whitelist
    _whitelist = _load_whitelist_from_disk()
    logger.info("Loaded %d user(s) from whitelist.", len(_whitelist))

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
