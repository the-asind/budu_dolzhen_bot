# Budu Dolzhen Bot

Budu Dolzhen Bot ("Буду Должен") is a Telegram bot for tracking shared expenses and debts between friends or group members. It parses free‑form messages, keeps confirmations transparent, and reminds participants about outstanding balances.

## Key Features

- **Natural language input** – Record debts using short messages like `@user1 1200 for coffee` or split amounts between several users: `я @user1 @user2 3000/3 торт`.
- **Arithmetic expressions** – Amounts can include basic `+`, `-`, `*` and `/` expressions.
- **Confirmation workflow** – Debtors confirm each entry via inline buttons to avoid disputes.
- **Payment tracking** – Register partial or full repayments with two‑sided confirmation.
- **Reminders and reports** – Weekly summaries and optional payday notifications via APScheduler.
- **Settings menu** – Manage contact details, reminder days and trusted users through an FSM‑driven interface.
- **Localization** – English and Russian message catalogues are included.
- **Repository pattern** – All data access is routed through asynchronous repositories using SQLite.

## Project Structure

```
bot/              # Application package
├─ core/          # Business logic: debt parsing, managers, notification service
├─ db/            # Database models, repositories and connection pool
├─ handlers/      # aiogram message and callback handlers
├─ keyboards/     # Inline keyboard factories
├─ locales/       # JSON translation files and i18n helpers
├─ middlewares/   # User, logging and i18n middlewares
├─ scheduler/     # Scheduled jobs (weekly reports, timeout checks)
└─ utils/         # Validators and helpers
```
Additional top‑level files:

- `main.py` – Entry point that starts the bot and scheduler.
- `docs/schema.sql` – Database schema used during initialization.
- `Dockerfile` and `docker-compose.yml` – Container configuration.
- `tests/` – Extensive pytest suite covering parsing, FSM flows and the scheduler.

## Requirements

- Python 3.12+
- Telegram Bot API token from [@BotFather](https://t.me/BotFather)
- (Optional) Docker and Docker Compose for containerized deployment

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/budu_dolzhen_bot.git
cd budu_dolzhen_bot

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt
```

### Environment configuration

Create a `.env` file in the project root with the following variables:

```
BOT_TOKEN=your_bot_token
BOT_ADMIN_ID=123456789
DATABASE_PATH=budu_dolzhen.db
LOG_LEVEL=INFO
SCHEDULER_TIMEZONE=UTC
```

`BOT_ADMIN_ID` is used for privileged commands and error notifications.

## Running the bot

### Locally

```bash
python main.py
```

### With Docker

```bash
docker-compose up --build
```

The container uses the same `.env` file and persists the SQLite database in the `data/` volume.

## Usage basics

- `/start` – Register with the bot and see onboarding instructions.
- `/help` – Detailed help with examples and tips.
- `/settings` – Open the profile settings menu (contact info, reminders, trusted users).
- **Recording debts** – Mention users with an amount and optional description. Example:
  `@alice @bob 900/3 dinner` – both users owe you 300 each.
- **Marking payments** – Send `скинул @alice 1000` in a private chat with the bot to log a payment.

The bot works in private chats and groups; pending confirmations expire after 23 hours if not accepted.

## Running tests

Development dependencies are listed in `requirements-dev.txt`.
Install them in your virtual environment and run:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Contributing

Issues and pull requests are welcome. Please ensure new features include tests and documentation.
