# speech_to_text_telegram-bot

A Telegram bot that transcribes voice messages and audio files using OpenAI's Whisper API.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your keys:
   - `TELEGRAM_BOT_TOKEN` — get one from [@BotFather](https://t.me/BotFather)
   - `OPENAI_API_KEY` — from [OpenAI](https://platform.openai.com/api-keys)

3. Run the bot:
   ```
   python bot.py
   ```

## Usage

Send a voice message or audio file to the bot and it will reply with the transcription.
