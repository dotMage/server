# server

Self-hosted, E2E-encrypted `.env` secret manager. The server stores only encrypted blobs — it **never** sees plaintext secrets.

**Footprint:** ~70–100 MB RAM idle for the whole stack (API + web admin; measured on arm64 and amd64), images 68 + 26 MB, all state in one SQLite file. Runs happily on a Raspberry Pi or the cheapest VPS.

## Deploy (one command)

```bash
# solo (default) — personal secrets vault
curl -fsSL https://raw.githubusercontent.com/dotMage/server/main/install.sh | bash

# team — same installer, one flag: enables users, invitations and roles
curl -fsSL https://raw.githubusercontent.com/dotMage/server/main/install.sh | DOTMAGE_MODE=team bash
```

That's it. Downloads the Docker image, creates `docker-compose.yml`, starts the server on port 8000, prints the bootstrap secret.

Upgrading an existing solo server to team: add `DOTMAGE_MODE: "team"` to the
`environment:` block in `docker-compose.yml` and run `docker compose up -d`. Existing
accounts migrate automatically (the owner becomes user #1); switching back to solo is
refused while more than one user exists.

Requires only Docker. No git, no Node.js, no Python, no Rust.

### Alternative: build from source

```bash
git clone https://github.com/dotMage/server.git
cd server
./build.sh
```

### Get the bootstrap secret

On first start, the server generates a one-time bootstrap code:

```bash
docker-compose logs server | grep "bootstrap secret"
# → [dotMage] Generated bootstrap secret: XXXXXXXXXXXX
```

### Connect your first device

Download `dmage` from [releases](https://github.com/dotMage/dotmage/releases), then:

```bash
dmage auth --server http://your-server:8000
# Enter the bootstrap secret and set your master password
# Done — push/pull from any directory

dmage init myapp          # push current .env
dmage pull myapp          # pull on another machine
dmage exec myapp -- npm start  # run with secrets in memory
```

### Add a second device

```bash
# On the first device:
dmage gen-token --name work-pc --ttl 1h

# On the new device:
dmage auth --server http://your-server:8000 --enroll dmage_etok_xxx
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DOTMAGE_DB_URL` | `sqlite:////data/dotmage.db` | Database connection string |
| `DOTMAGE_BOOTSTRAP_SECRET` | _(auto-generated)_ | One-time secret for first device |
| `DOTMAGE_TOKEN_TTL` | `24h` | Device token lifetime |
| `DOTMAGE_REFRESH_TTL` | `30d` | Refresh token lifetime |
| `DOTMAGE_RATE_LIMIT` | `10/min` | Rate limit on auth endpoints |
| `DOTMAGE_LOG_LEVEL` | `info` | Log level |

## Production (TLS)

In production, put the server behind a reverse proxy with auto-TLS. Example with Caddy:

```yaml
# docker-compose.prod.yml
services:
  server:
    build: .
    restart: unless-stopped
    environment:
      DOTMAGE_DB_URL: "sqlite:////data/dotmage.db"
    volumes:
      - dotmage-data:/data
    expose:
      - "8000"

  proxy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
    depends_on:
      - server

volumes:
  dotmage-data:
  caddy-data:
```

```
# Caddyfile
secrets.example.com {
    reverse_proxy server:8000
}
```

## Backup & restore

```bash
# online backup, safe while the server is running (the image has no sqlite3 CLI — use python)
docker compose exec server python -c "import sqlite3; s=sqlite3.connect('/data/dotmage.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close()"
docker compose cp server:/data/backup.db ./backup-$(date +%F).db
```

Losing the database = losing access to all secrets, even with the master password — the server
cannot restore what it never sees (E2E). **Backup is critical.**

Full runbook — cron schedule, backup verification, step-by-step restore:
[dotmage.github.io/docs/#backup](https://dotmage.github.io/docs/#backup)

## Web Admin

The web admin panel is built into the Docker image automatically. Access it at `http://your-server:8000/` and log in with a device token.

The admin panel shows **only metadata** (app names, revisions, devices, audit log). It cannot display secret values — the server never has them.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

## Contributing

Every user-visible change updates `CHANGELOG.md` under `[Unreleased]` in the same PR —
entries are written for users, not committers. API contract changes go through the
private `dotmage-spec` repo first.

## License

AGPL-3.0 — see [LICENSE](LICENSE).
