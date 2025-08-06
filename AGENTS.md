# Agent Guidelines

These instructions apply to the entire repository. Follow them when modifying or adding any files.

## Project overview
- Python 3.12+ with [aiogram](https://docs.aiogram.dev/en/latest/) 3.x.
- Telegram-specific logic lives in `bot/handlers/`.
- Database access and models live in `bot/db/`.
- Reusable helpers go to `bot/utils/`.
- Do **not** mix SQL queries with handlers; always use the repository layer and parameterized `?` placeholders with SQLite/aiosqlite.

## Repository layout
- `bot/` – application package
  - `core/` business logic
  - `db/` SQLite models and repositories
  - `handlers/` aiogram message and callback handlers
  - `keyboards/` inline keyboards
  - `locales/`, `middlewares/`, `scheduler/`, `utils/`
- `tests/` – pytest suite
- `docs/schema.sql` – database schema
- `main.py` – entry point

## Style
- Format with **black** using 120 characters per line:
  ```bash
  python -m black . --line-length 120
  ```
- Lint with **ruff** and fix issues before committing:
  ```bash
  python -m ruff .
  ```
- Follow PEP8, use type hints and `@dataclass` for simple data containers.
- Public classes and functions require Google‑style docstrings.
- Keep modules focused on a single responsibility; split files >400 LOC or functions >30 LOC.

## Testing
1. When adding behaviour, write or update tests in `tests/` first (`pytest` + `pytest-asyncio`).
2. Ensure new tests fail before implementation and pass afterwards.
3. Run the full test suite and coverage:
   ```bash
   pytest --cov=bot
   ```
   The `bot/` package must keep ≥80 % coverage.

## Security
- Never commit secrets, tokens, or database dumps. Load configuration from environment variables (see `.env.example`).
- Avoid `eval`, `exec`, or raw SQL string concatenation.
- Validate user input: amounts are non‑negative integers; usernames match `^@[A-Za-z0-9_]{5,}$`.

## Logging
- Use the standard `logging` module (format `%(asctime)s %(levelname)s [%(name)s] %(message)s`). Avoid `print`.

## Commits & PRs
- Use **Conventional Commit** messages (`feat:`, `fix:`, `refactor:`, etc.).
- Run formatter, linter and tests before each commit/PR.
- Update `README.md` or `docs/` when behaviour or public APIs change.