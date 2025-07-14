# Budu Dolzhen Bot

"Budu Dolzhen" (a Russian play on words for "I'll be in your debt") is a Telegram bot designed to help friends track shared expenses and debts. It allows for quick, natural language input to record who owes whom, handles confirmations, tracks payments, and provides summaries, all within Telegram.

## Features

- **Natural Language Debt Parsing:** Add debts with simple messages like `@user1 @user2 1500 for pizza`.
- **Expression Support:** Calculate amounts on the fly: `@friend 3000/3 for a shared gift`.
- **Debt Confirmation:** All debts require confirmation from the debtor, ensuring fairness and preventing fraud.
- **Payment Tracking:** Mark debts as partially or fully paid, with confirmation from the creditor.
- **User Settings:** Configure payment details, reminders, and trusted users via an inline menu.
- **Scheduled Reminders:** Get weekly summaries and payday reminders to settle up.
- **Multi-language Support:** Currently supports English and Russian.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for containerized deployment)
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/budu-dolzhen-bot.git
    cd budu-dolzhen-bot
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```

2.  Edit the `.env` file and fill in your details:
    - `BOT_TOKEN`: Your Telegram bot token.
    - `ADMIN_ID`: The Telegram user ID of the bot administrator.
    - `DATABASE_PATH`: The path to the SQLite database file (e.g., `data/bot.db`).
    - `LOG_LEVEL`: The logging level (e.g., `INFO`, `DEBUG`).

## Usage

### Running the Bot

#### Locally

To run the bot directly using Python:

```bash
python main.py
```

#### With Docker

To run the bot in a Docker container:

1.  Make sure your `.env` file is configured.
2.  Build and run the container in detached mode:
    ```bash
    docker-compose up --build -d
    ```

### Interacting with the Bot

- **/start**: Initializes the bot and registers you as a user.
- **/help**: Shows a detailed help message with command examples.
- **/settings**: Opens the user settings menu to manage your contact info, reminders, and trusted users.
- **Adding a debt**: Simply send a message in a private chat or a group with the format `@username <amount> [description]`.

## Project Architecture

The bot is built using `aiogram` and follows a modular structure to separate concerns:

- `main.py`: The main entrypoint that initializes the bot, dispatcher, and all components.
- `bot/`: The core application package.
  - `core/`: Contains the main business logic (debt parsing, managers).
  - `db/`: Handles database connections, models, and repositories.
  - `handlers/`: Contains all the message and callback query handlers.
  - `keyboards/`: Functions for generating inline keyboards.
  - `locales/`: Localization files for multi-language support.
  - `middlewares/`: Custom middlewares for logging, user management, and i18n.
  - `scheduler/`: Logic for scheduled tasks like reminders.
  - `utils/`: Shared utility functions (validators, formatters).
- `docs/`: Contains the database schema (`schema.sql`).
- `tests/`: Contains tests for the application (currently a work in progress).
- `Dockerfile` & `docker-compose.yml`: For containerized deployment.

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/the-asind/budu_dolzhen_bot?utm_source=oss&utm_medium=github&utm_campaign=the-asind%2Fbudu_dolzhen_bot&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
