#!/usr/bin/env bash
set -e

# Start FastAPI app (use PORT provided by Render)
PORT=${PORT:-8000}

# Run uvicorn in background
uvicorn app:app --host 0.0.0.0 --port ${PORT} &
UVICORN_PID=$!

# Start train notification service in background (with monitoring)
python train_notification_service.py --start &
TRAIN_PID=$!

# Start telegram bot in foreground (keeps the service alive)
python telegram_bot.py

# On exit, kill background processes
kill ${UVICORN_PID} ${TRAIN_PID} || true
