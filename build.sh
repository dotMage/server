#!/bin/bash
set -e

WEB_DIR="web"

# 1. Clone or update web admin
if [ -d "$WEB_DIR/.git" ]; then
    echo "Updating dotmage-web..."
    git -C "$WEB_DIR" pull --ff-only
else
    echo "Cloning dotmage-web..."
    rm -rf "$WEB_DIR"
    git clone --depth 1 git@github.com:dotMage/dotmage-web.git "$WEB_DIR"
fi

# 2. Build web admin
echo "Building web admin..."
(cd "$WEB_DIR" && npm ci && npm run build)

# 3. Build and start
echo "Building Docker image..."
docker compose build

echo ""
echo "Ready. Run:  docker compose up -d"
echo "Admin panel: http://localhost:8000"
echo "Bootstrap:   docker compose logs server | grep 'bootstrap secret'"
