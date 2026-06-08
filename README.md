# dotmage-server

API backend for [dotMage](https://github.com/dotMage) — a self-hosted, E2E-encrypted `.env` secret manager.

The server is a "dumb" storage of encrypted blobs. It **never** sees plaintext secrets — all encryption happens client-side.

## Quick start

```bash
docker compose up -d
```

The server prints a bootstrap secret on first start — check the logs:

```bash
docker compose logs server | grep "bootstrap secret"
```

Use this secret when running `dmage auth` on your first device.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DOTMAGE_DB_URL` | `sqlite:////data/dotmage.db` | Database connection string |
| `DOTMAGE_BOOTSTRAP_SECRET` | _(auto-generated)_ | One-time secret for first device registration |
| `DOTMAGE_TOKEN_TTL` | `24h` | Device token lifetime |
| `DOTMAGE_REFRESH_TTL` | `30d` | Refresh token lifetime |
| `DOTMAGE_RATE_LIMIT` | `10/min` | Rate limit on auth endpoints |
| `DOTMAGE_LOG_LEVEL` | `info` | Log level |
| `DOTMAGE_STATIC_DIR` | `/app/static` | Path to web admin static files |

## Deployment with TLS

dotMage requires HTTPS in production. Use a reverse proxy like Caddy:

```
# Caddyfile
secrets.example.com {
    reverse_proxy server:8000
}
```

See the [spec](https://github.com/dotMage/dotmage-spec) for full deployment details (Appendix H).

## Backup

The SQLite database contains only encrypted blobs, but losing it means losing access to all secrets (even with the master password).

```bash
# Backup
docker compose exec server sqlite3 /data/dotmage.db ".backup /data/backup-$(date +%F).db"

# Restore
docker compose down
cp backup.db data/dotmage.db
docker compose up -d
```

## API

Full API contract is documented in [dotmage-spec](https://github.com/dotMage/dotmage-spec) (Appendix B).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/account/init` | Bootstrap account |
| GET | `/api/v1/account/keys` | Get wrapped encryption keys |
| PATCH | `/api/v1/account/keys` | Update keys (password change) |
| POST | `/api/v1/auth/device` | Register device |
| POST | `/api/v1/auth/refresh` | Refresh tokens |
| GET/POST | `/api/v1/apps` | List/create apps |
| GET/POST/DELETE | `/api/v1/apps/{name}/envs[/{env}]` | Manage environments |
| GET/POST | `/api/v1/apps/{name}/envs/{env}/revisions[/{rev}]` | Push/pull/history |
| POST | `/api/v1/apps/{name}/envs/{env}/rollback` | Rollback |
| GET/DELETE | `/api/v1/devices[/{id}]` | List/revoke devices |
| POST | `/api/v1/devices/enroll-token` | Generate enrollment token |
| GET | `/api/v1/audit` | Audit log |

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
