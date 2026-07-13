# MultiLingo (Trichy)

A FastAPI-based web app and worker for multilingual text translation, TTS audio generation, and Telegram-based train notifications.

## Quick overview
- Web app: `app.py` (FastAPI)
- Notification worker: `train_notification_service.py`
- Telegram bot: `telegram_bot.py` (polling)
- Mock train API: `mock_train_api.py` (for local/demo)
- Static frontend under `static/`

## Environment variables
Set the following when deploying (Render, Docker, or locally via `.env`):

- `TELEGRAM_BOT_TOKEN` — (required) Telegram Bot token
- `TELEGRAM_BOT_USERNAME` — (optional) Bot username (used for QR links)
- `GEMINI_API_KEY` — (optional) Google Gemini / GenAI API key for improved translations
- `DB_PATH` — (optional) path to SQLite DB (defaults to `./users.db`)
- `APP_URL` — (optional) public URL to the web app (used by the bot for internal API calls). Defaults to `http://localhost:8000` when not set locally.
- `MOCK_API_URL` — (optional) mock train API base (defaults to `http://127.0.0.1:5001/api`)

## Run locally (development)
1. Create and activate a virtualenv (Windows PowerShell example):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. (Optional) Create a `.env` with your environment values. Example `.env`:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_key
DB_PATH=./users.db
APP_URL=http://localhost:8000
MOCK_API_URL=http://127.0.0.1:5001/api
```

3. Start components (single-service quick start):

```bash
# From repo root
bash ./start.sh
```

Or run components separately for debugging:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
python train_notification_service.py
python telegram_bot.py
```

Notes:
- The `start.sh` script runs the FastAPI app, the notification worker, and the Telegram bot together (useful for Render single-service deployments where they share the same filesystem for SQLite).
- For Windows you can run the three commands in separate PowerShell tabs.

## Render deployment
1. Add the repository to Render.
2. Set environment variables in the Render dashboard (the same list under "Environment variables").
3. Build command (already in `render.yaml`):

```
pip install -r requirements.txt
```

4. Start command (already in `render.yaml`):

```
bash ./start.sh
```

Important: ensure `DB_PATH` points to a persistent path that Render provides (or use the default `./users.db` so the DB lives inside the repo volume for the service). Render's single service will keep the filesystem shared between processes.

## Frontend configuration
- The dashboard and HTML pages default to calling the local API at the same origin (`/api`) so deploying behind Render's web service works without CORS changes.
- If you host the mock API separately, set `window.TRAIN_API_BASE` or `window.API_BASE` in the HTML template to point to the external API.

## Security & secrets
- The code now reads secrets via environment variables; please DO NOT commit real secrets to the repo.
- The repo contains default fallback tokens/keys (for local testing only). Override them using env vars in production.

## Verification steps I performed
- Replaced hardcoded tokens and API URLs with environment-configurable values.
- Added `start.sh` and `render.yaml` for Render single-service deployment.
- Updated frontend JS to prefer same-origin API calls.

## Next recommended steps
- Configure Render environment variables and deploy using `render.yaml`.
- Run local smoke tests (signup/login, generate audio, link Telegram, subscribe to a train).
- If you want, I can run a grep-based audit, try a local smoke start (install + start), or prepare a Dockerfile.

