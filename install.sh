#!/bin/bash
set -e

PORT_API=9470
PORT_WEB=9471
DIR="dotmage"
# solo (default) or team: curl ... | DOTMAGE_MODE=team bash
MODE="${DOTMAGE_MODE:-solo}"

printf "\n"
printf "  \e[36m.  dotMage installer  .\e[0m\n"
printf "\n"

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

printf "  Pulling images...\n"
$DC pull -q 2>/dev/null || $DC pull

printf "  Starting services...\n"
$DC up -d 2>/dev/null

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
printf "\n"

if [ "$MODE" = "team" ]; then
    printf "\n"
    printf "  Team mode is ON. After dmage auth, invite members:\n"
    printf "    dmage user invite <name> --role editor\n"
fi
