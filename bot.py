import logging
import os
import tempfile

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a voice message or audio file and I'll transcribe it (Armenian supported)."
    )


def estimate_cost(usage) -> str:
    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0
    input_cost = (input_tokens / 1_000_000) * AUDIO_INPUT_COST_PER_M
    output_cost = (output_tokens / 1_000_000) * TEXT_OUTPUT_COST_PER_M
    total = input_cost + output_cost
    return (
        f"tokens: {input_tokens} in / {output_tokens} out | "
        f"cost: ${total:.5f}"
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    audio = update.message.voice or update.message.audio
    file = await audio.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        await file.download_to_drive(tmp.name)

        with open(tmp.name, "rb") as f:
            audio_bytes = f.read()

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
            "Transcribe this audio in Armenian. Return only the transcription, nothing else.",
        ],
    )

    text = (response.text or "").strip()
    if not text:
        await update.message.reply_text("(empty transcription)")
        return

    cost_line = estimate_cost(response.usage_metadata)
    await update.message.reply_text(f"{text}\n\n_{cost_line}_", parse_mode="Markdown")


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.run_polling()


if __name__ == "__main__":
    main()
