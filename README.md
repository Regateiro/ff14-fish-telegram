# FFXIV Flying Fish Bot

A Telegram bot that monitors FFXIV fish availability using the [ff14-fish-tracker-app](https://github.com/icykoneko/ff14-fish-tracker-app) data. Tracks caught fish per user and sends reminders before fish windows open.

## Commands

- `/start` — Show help
- `/caught [name|all]` — List caught fish, or mark a fish as caught
- `/uncaught [name|all]` — List uncaught fish, or mark a fish uncaught
- `/day` — List uncaught fish available in the next 24 hours

Reminders are sent automatically for uncaught fish when a catch window approaches (10 min lead for direct fish, 30 min for fish requiring mooching or intuition).

## Setup

```bash
cp .env.example .env   # fill in TELEGRAM_TOKEN
make install
make run
```

## Development

```bash
make lint      # ruff check
make format    # ruff format
make test      # pytest
```
