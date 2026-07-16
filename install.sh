#!/bin/bash
set -e

PORT_API=9470
PORT_WEB=9471
DIR="dotmage"
# solo (default) or team: curl ... | DOTMAGE_MODE=team bash
MODE="${DOTMAGE_MODE:-solo}"
# optional display name clients adopt: curl ... | DOTMAGE_SERVER_NAME=work bash
SERVER_NAME="${DOTMAGE_SERVER_NAME:-}"

printf "\n"
printf "  \e[36m.  dotMage installer  .\e[0m\n"
printf "\n"

# Interactive prompts — work even under `curl ... | bash` by reading the
# terminal directly (/dev/tty). Env vars, when set, skip the prompt.
if [ -t 0 ] || [ -e /dev/tty ]; then
    if [ -z "${DOTMAGE_MODE:-}" ]; then
        printf "  Mode — [1] solo (personal)  [2] team (shared, invites + roles) [1]: "
        read -r ans < /dev/tty || ans=""
        [ "$ans" = "2" ] && MODE="team"
    fi
    if [ "$MODE" = "team" ] && [ -z "${DOTMAGE_SERVER_NAME:-}" ]; then
        printf "  Server name shown to clients (e.g. work) [optional]: "
        read -r ans < /dev/tty || ans=""
        [ -n "$ans" ] && SERVER_NAME="$ans"
    fi
fi
printf "  Mode: \e[1m%s\e[0m" "$MODE"
[ -n "$SERVER_NAME" ] && printf "   Name: \e[1m%s\e[0m" "$SERVER_NAME"
printf "\n\n"

mkdir -p "$DIR"
cd "$DIR"

cat > docker-compose.yml << EOF
services:
  server:
    image: ghcr.io/dotmage/server:latest
    restart: unless-stopped
    environment:
      DOTMAGE_DB_URL: "sqlite:////data/dotmage.db"
      DOTMAGE_BOOTSTRAP_SECRET: ""
      DOTMAGE_TOKEN_TTL: "24h"
      DOTMAGE_REFRESH_TTL: "30d"
      DOTMAGE_LOG_LEVEL: "info"
      DOTMAGE_MODE: "${MODE}"
      DOTMAGE_SERVER_NAME: "${SERVER_NAME}"
    volumes:
      - dotmage-data:/data
    ports:
      - "${PORT_API}:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  web:
    image: ghcr.io/dotmage/web:latest
    restart: unless-stopped
    ports:
      - "${PORT_WEB}:80"

volumes:
  dotmage-data:
EOF

# Detect docker compose command
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    DC="docker-compose"
else
    printf "  \e[31mError:\e[0m docker compose not found\n" >&2
    exit 1
fi

# Verify we can actually talk to the docker daemon: `docker compose version`
# succeeds without socket access, but pull/up would fail with permission denied.
if ! docker info >/dev/null 2>&1; then
    printf "  \e[31mError:\e[0m cannot connect to the Docker daemon (permission denied?)\n" >&2
    printf "  Re-run with sudo, or add yourself to the docker group and re-login:\n" >&2
    printf "    sudo usermod -aG docker %s\n" "$USER" >&2
    exit 1
fi

printf "  Pulling images...\n"
$DC pull -q 2>/dev/null || $DC pull

printf "  Starting services...\n"
$DC up -d

# Detect public IP
PUBLIC_IP=$(curl -s --max-time 3 ifconfig.me 2>/dev/null \
         || curl -s --max-time 3 icanhazip.com 2>/dev/null \
         || hostname -I 2>/dev/null | awk '{print $1}' \
         || echo "localhost")

API_URL="http://${PUBLIC_IP}:${PORT_API}"
WEB_URL="http://${PUBLIC_IP}:${PORT_WEB}"

printf "\n"
printf "  \e[32m[ok] dotMage is running\e[0m\n"
printf "\n"
printf "  API:           %s\n" "$API_URL"
printf "  Admin Panel:   %s\n" "$WEB_URL"
printf "\n"

sleep 3
SECRET=$($DC logs server 2>&1 | grep "bootstrap secret" | sed 's/.*secret: //' | tail -1)

if [ -n "$SECRET" ]; then
    printf "  Bootstrap secret (save it!):  \e[1m%s\e[0m\n" "$SECRET"
else
    printf "  Bootstrap secret not ready yet. Run:\n"
    printf "  cd %s && %s logs server | grep 'bootstrap secret'\n" "$DIR" "$DC"
fi

printf "\n"
printf "  -- Next steps --\n"
printf "\n"
printf "  1. Download CLI:  https://github.com/dotMage/dotmage/releases\n"
printf "  2. Authenticate:  dmage auth --server %s\n" "$API_URL"
printf "  3. Push secrets:  cd your-project && dmage init myapp\n"
printf "  4. Admin panel:   %s\n" "$WEB_URL"
printf "  5. Set up backups (E2E: the server cannot recover a lost DB):\n"
printf "     https://dotmage.github.io/docs/#backup\n"
printf "\n"

if [ "$MODE" = "team" ]; then
    printf "\n"
    printf "  Team mode is ON. After dmage auth, invite members:\n"
    printf "    dmage user invite <name> --role editor\n"
fi
