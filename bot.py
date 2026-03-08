import logging
import os
import tempfile

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Gemini 2.5 Flash pricing (per 1M tokens)
AUDIO_INPUT_COST_PER_M = float(os.getenv("AUDIO_INPUT_COST_PER_M", "1.00"))
TEXT_OUTPUT_COST_PER_M = float(os.getenv("TEXT_OUTPUT_COST_PER_M", "2.00"))

gemini_client = genai.Client()

TRANSCRIBE_PROMPT = (
    "Transcribe this audio in Armenian. Return only the transcription, nothing else."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a voice message or audio file and I'll transcribe it (Armenian supported)."
    )


def format_cost(usage) -> str:
    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    input_cost = (input_tokens / 1_000_000) * AUDIO_INPUT_COST_PER_M
    output_cost = (output_tokens / 1_000_000) * TEXT_OUTPUT_COST_PER_M
    total = input_cost + output_cost
    return (
        f"tokens: {input_tokens} in / {output_tokens} out | "
        f"cost: ${total:.5f}"
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    audio = update.message.voice or update.message.audio or update.message.video_note
    if not audio:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    tg_file = await audio.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        await tg_file.download_to_drive(tmp.name)
        with open(tmp.name, "rb") as f:
            audio_bytes = f.read()

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                TRANSCRIBE_PROMPT,
            ],
        )
    except Exception:
        logger.exception("Gemini API error")
        await update.message.reply_text("Transcription failed. Please try again.")
        return

    text = (response.text or "").strip()
    if not text:
        await update.message.reply_text("(empty transcription)")
        return

    cost_line = format_cost(response.usage_metadata)
    await update.message.reply_text(
        f"{text}\n\n<i>{cost_line}</i>", parse_mode="HTML"
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, handle_audio)
    )
    app.run_polling()


if __name__ == "__main__":
    main()
