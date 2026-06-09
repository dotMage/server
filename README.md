# server

Self-hosted, E2E-encrypted `.env` secret manager. The server stores only encrypted blobs — it **never** sees plaintext secrets.

## Deploy (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/dotMage/server/main/install.sh | bash
```

That's it. Downloads the Docker image, creates `docker-compose.yml`, starts the server on port 8000, prints the bootstrap secret.

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

## Backup

```bash
docker-compose exec server sqlite3 /data/dotmage.db ".backup /data/backup-$(date +%F).db"
```

Losing the database = losing access to all secrets, even with the master password. **Backup is critical.**

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

## License

AGPL-3.0 — see [LICENSE](LICENSE).
