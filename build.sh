#!/bin/bash
set -e

WEB_DIR="web"

# Detect docker compose command (v2 plugin or v1 standalone)
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif docker-compose version >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Error: docker compose not found. Install Docker with Compose plugin." >&2
    exit 1
fi

echo "Using: $DC"

# 1. Clone or update web admin
if [ -d "$WEB_DIR/.git" ]; then
    echo "Updating web..."
    git -C "$WEB_DIR" pull --ff-only
else
    echo "Cloning web..."
    rm -rf "$WEB_DIR"
    git clone --depth 1 https://github.com/dotMage/web.git "$WEB_DIR"
fi

# 2. Build web admin inside Docker (no Node.js needed on host)
echo "Building web admin (in Docker)..."
docker run --rm \
    -v "$(pwd)/$WEB_DIR":/build \
    -w /build \
    node:22-slim \
    sh -c "npm ci && npm run build"

# 3. Build server image and start
echo "Building server..."
$DC build
$DC up -d

echo ""
echo "dotMage is running at http://localhost:8000"
echo ""
echo "Bootstrap secret:"
sleep 2
$DC logs server 2>&1 | grep -i "bootstrap secret" || echo "(wait a few seconds, then run: $DC logs server | grep 'bootstrap secret')"
