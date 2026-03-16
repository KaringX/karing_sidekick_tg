## Purpose
This repository is currently empty except for `.git/`.
There is no existing code, build config, test config, Cursor rules, Copilot
instructions, or prior root `AGENTS.md` to inherit from.

Use this file as the working guide for agentic coding in this repo.
The intended project is a small test system that reads Telegram group or
channel content and, each day, extracts 1-3 article candidates focused on app
usage tutorials, troubleshooting, and practical fixes.

## Current State
- No commits yet.
- No source files, dependency files, or runnable commands yet.
- No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md`
  were found.
- Do not claim any command or convention is already enforced by the repo.
- When scaffolding, prefer the smallest useful implementation.

## Recommended Baseline
Because the repo is empty, standardize on Python unless the user requests
another stack.

- Python 3.12+
- `uv` for environment and dependency management if available
- `pytest` for tests
- `ruff` for linting and formatting
- `mypy` for type checking
- `src/` layout

Suggested layout:
- `src/tg_digest/` application package
- `tests/` automated tests
- `scripts/` manual utilities
- `docs/` notes and operational docs
- `.env.example` documented environment variables only

## Canonical Commands
The repo does not currently define commands. If you scaffold the project, keep
these stable so later agents can rely on them.

### Environment
- Create env: `uv venv`
- Install deps: `uv sync`
- Run app: `uv run python -m tg_digest`

If `uv` is unavailable:
- Create env: `python -m venv .venv`
- Activate env: `source .venv/bin/activate`
- Install deps: `pip install -e .[dev]`

### Build
- Package build: `uv run python -m build`
- If packaging is not set up, do not invent a build step.
- For app-only work, passing lint, type checks, and tests is enough.

### Lint and Format
- Lint: `uv run ruff check .`
- Auto-fix lint issues: `uv run ruff check . --fix`
- Format: `uv run ruff format .`
- Format check only: `uv run ruff format --check .`
- Type check: `uv run mypy src tests`

### Tests
- Full suite: `uv run pytest`
- One file: `uv run pytest tests/test_fetcher.py`
- One test: `uv run pytest tests/test_fetcher.py::test_parse_post`
- By keyword: `uv run pytest -k parse_post`
- Verbose single test: `uv run pytest -vv tests/test_fetcher.py::test_parse_post`
- Stop on first failure: `uv run pytest -x`
- Re-run last failures: `uv run pytest --lf`

### Coverage
- If coverage is configured: `uv run pytest --cov=src/tg_digest --cov-report=term-missing`
- Do not add coverage tooling unless the project actually uses it.

## Completion Standard
Before finishing a non-trivial change, try to run:
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src tests`
- `uv run pytest`

If the project is only partially scaffolded, run the subset that exists and say
exactly what could not be executed.

## Code Style
Since there is no existing code to mirror, use these defaults.

### Imports
- Group imports as standard library, third-party, then local.
- Prefer absolute imports from `tg_digest`.
- Avoid wildcard imports.
- Import only what is used.
- Avoid module-level side effects unless required.

### Formatting
- Follow `ruff format` defaults.
- Use 4 spaces for indentation.
- Keep lines readable; target 88-100 columns.
- Prefer small functions and early returns over deep nesting.
- Add comments only when a block is not obvious from the code.

### Types
- Type all public functions, methods, and module constants.
- Prefer concrete types over `Any`.
- Use `dataclass`, `TypedDict`, and `Protocol` where they clarify boundaries.
- Type external API payloads at the parsing boundary.
- Return structured values instead of loose dicts when practical.

### Naming
- Modules and packages: `snake_case`
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Test files: `test_*.py`
- Test names should describe behavior, not implementation details.

### Error Handling
- Fail loudly on programmer errors.
- Catch narrow exception types.
- Raise domain-specific exceptions when callers can recover.
- Include actionable context in error messages.
- Never log secrets, tokens, or raw credentials.

### Configuration
- Read secrets from environment variables or a local `.env` file.
- Commit `.env.example`, never real credentials.
- Centralize config parsing in one module.
- Validate required config at startup.

### Telegram and Content Rules
- Separate Telegram I/O from ranking, filtering, and article generation.
- Make fetching idempotent where possible.
- Store source message IDs for deduplication.
- Normalize timestamps to UTC internally.
- Keep selection logic deterministic for tests.
- Keep outputs focused on app tutorials and problem-solving topics.

### Testing Rules
- Prefer unit tests for parsing, filtering, ranking, and scheduling.
- Mock Telegram network calls in unit tests.
- Use fixtures for representative message payloads.
- Add regression tests for bug fixes.
- Inject a clock for time-dependent logic.

## Agent Expectations
- Read the repo before making assumptions.
- If the repo is still empty, scaffold the minimum viable structure first.
- Keep dependencies small and justified.
- Prefer file-backed prototypes before adding services or databases.
- Update `README.md` once the project has runnable commands.
- Document each new script, entry point, and environment variable.

## Future Rule Files
If `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` are
added later, treat them as higher-priority repo guidance and merge their intent
into future updates of this file.

## Good First Steps
- Scaffold `src/tg_digest/` and `tests/`.
- Add a Telegram ingestion abstraction.
- Add daily selection logic for 1-3 article candidates.
- Add tests for parsing, filtering, ranking, and scheduling.
- Add a simple runner or scheduled entry point.
