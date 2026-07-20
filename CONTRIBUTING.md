# Contributing to dotMage server

The API backend for dotMage — an E2E-encrypted `.env` secret manager. The server
stores only encrypted blobs; it never sees plaintext secrets. Keep it that way.

## Development setup

Requires Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run locally

```bash
DOTMAGE_DB_URL="sqlite:////tmp/dotmage-dev.db" \
DOTMAGE_BOOTSTRAP_SECRET="dev-secret" \
uvicorn main:app --reload --port 8000
```

`GET /health` should return `{"status":"ok","version":"…"}`. Key settings
(`src/settings.py`, prefix `DOTMAGE_`): `DB_URL`, `BOOTSTRAP_SECRET`, `MODE`
(`solo`|`team`), `TOKEN_TTL`, `REFRESH_TTL`, `WEB_PORT`.

To build and run the whole stack (server + web admin) from source in Docker:

```bash
./build.sh
```

## Checks (run before opening a PR — CI runs the same)

```bash
ruff check src/ tests/
mypy src/ --ignore-missing-imports
pytest tests/ -v
```

## Project layout

```
main.py              FastAPI app factory
src/settings.py      env-var configuration
src/api/v1/…         routers (auth, apps, revisions, devices, users, rotation, audit); /health is separate
src/core/            services, auth/crypto helpers, DB + repositories
src/models/          SQLAlchemy models
src/enums/           enums (audit actions, …)
tests/               pytest suite
```

## Ground rules

- **Never log or persist plaintext secrets.** The server handles only ciphertext
  and hashed tokens. If a change could expose a secret value, it's wrong.
- **The API is a contract.** It's versioned by URL (`/api/v1`). A breaking change
  means `/api/v2`, not a silent edit — the contract lives in the private
  `dotmage-spec` repo and changes there are visible PRs.
- **Version lives in `pyproject.toml`.** `/health` reads it from the installed
  package metadata (`src/version.py`); don't hardcode it elsewhere.
- **Migrations are additive.** New columns get a startup `ALTER TABLE`; don't
  break reads for older clients within a major.

## Commits & PRs

Short, imperative commit subjects (Conventional Commits style: `feat:`, `fix:`,
`ci:`, `docs:`). Keep the CHANGELOG's `[Unreleased]` section current. Releases are
cut from an annotated `vX.Y.Z` tag — pushing to `main` builds nothing user-facing.
