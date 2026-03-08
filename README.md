# speech_to_text_telegram-bot

A Telegram bot that transcribes Armenian voice messages using Google's Gemini API. Reports cost per transcription.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your keys:
   - `TELEGRAM_BOT_TOKEN` — get one from [@BotFather](https://t.me/BotFather)
   - `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/apikey)

3. Run the bot:
   ```
   python bot.py
   ```

## Usage

Send a voice message or audio file to the bot and it will reply with the transcription and cost breakdown.
