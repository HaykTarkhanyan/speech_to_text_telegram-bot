# Armenian Speech-to-Text Telegram Bot

A minimalistic private Telegram bot that transcribes Armenian voice messages and audio files using **Google Gemini** (the same model family powering YouTube captions).

---

## Features

- 🎙️ Transcribes Armenian voice messages and audio files
- 🔒 Private: only whitelisted users can interact with the bot
- 👤 Admin-controlled whitelist (add / remove / list users)
- ⚡ Powered by Google Gemini 1.5 Flash

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11 + |
| pip | latest |

---

## 1 — Create the Telegram Bot

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username.
3. Copy the **bot token** BotFather gives you (looks like `1234567890:ABCdef…`).

---

## 2 — Get a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with a Google account and click **Create API key**.
3. Copy the key.

---

## 3 — Find Your Telegram User ID

1. Start a chat with [@userinfobot](https://t.me/userinfobot) on Telegram.
2. It will reply with your **User ID** (a plain number like `123456789`).
   This is the `ADMIN_USER_ID` — you will be the only person who can manage the whitelist.

---

## 4 — Local Setup

```bash
# Clone the repo
git clone https://github.com/HaykTarkhanyan/speech_to_text_telegram-bot.git
cd speech_to_text_telegram-bot

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in the three values:
#   TELEGRAM_BOT_TOKEN=...
#   GEMINI_API_KEY=...
#   ADMIN_USER_ID=...

# Run the bot
python bot.py
```

---

## 5 — Deploying to a Server (e.g. a VPS or Render)

### Option A — systemd on a Linux VPS

```bash
# Copy files to the server, then create a service file
sudo nano /etc/systemd/system/stt-bot.service
```

Paste the following (adjust paths):

```ini
[Unit]
Description=Armenian STT Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/stt-bot
ExecStart=/opt/stt-bot/.venv/bin/python bot.py
EnvironmentFile=/opt/stt-bot/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stt-bot
sudo systemctl status stt-bot   # check it is running
```

### Option B — Docker

```bash
# Build
docker build -t stt-bot .

# Run (pass env vars from your .env file)
docker run -d --env-file .env --restart unless-stopped stt-bot
```

### Option C — Render (free tier)

1. Push your repo to GitHub.
2. Create a new **Background Worker** service on [Render](https://render.com).
3. Set the build command to `pip install -r requirements.txt` and the start command to `python bot.py`.
4. Add the three environment variables in the Render dashboard.

---

## 6 — Usage

| Command | Who can use | Description |
|---------|-------------|-------------|
| `/start` | Whitelisted users | Welcome message |
| `/whitelist_add <user_id>` | Admin only | Add a user to the whitelist |
| `/whitelist_remove <user_id>` | Admin only | Remove a user from the whitelist |
| `/whitelist_list` | Admin only | Show all whitelisted user IDs |
| Send a voice message or audio file | Whitelisted users | Transcribe the audio |

### Adding users

Send the following to the bot as the admin:

```
/whitelist_add 987654321
```

The user with ID `987654321` can now send voice messages to the bot.

---

## Project Structure

```
.
├── bot.py            # Main bot code
├── Dockerfile        # Container image definition
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── .env              # Your secrets (never committed)
└── whitelist.json    # Persisted whitelist (auto-created, never committed)
```

---

## Security Notes

- `.env` and `whitelist.json` are listed in `.gitignore` — never commit them.
- Only the `ADMIN_USER_ID` can modify the whitelist; non-admin users attempting to use admin commands will receive an authorisation error from the bot.
- The Gemini File API deletes uploaded audio automatically after 48 hours; the bot also requests immediate deletion after transcription.