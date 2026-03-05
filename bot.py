import logging
import os
import tempfile

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
openai_client = OpenAI()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a voice message or audio file and I'll transcribe it for you."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file = await (update.message.voice or update.message.audio).get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        await file.download_to_drive(tmp.name)
        transcription = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=open(tmp.name, "rb"),
        )

    text = transcription.text.strip()
    if not text:
        await update.message.reply_text("(empty transcription)")
        return

    await update.message.reply_text(text)


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.run_polling()


if __name__ == "__main__":
    main()
