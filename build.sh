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
    git clone --depth 1 https://github.com/dotMage/dotmage-web.git "$WEB_DIR"
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
docker-compose build
docker-compose up -d

echo ""
echo "dotMage is running at http://localhost:8000"
echo ""
echo "Bootstrap secret:"
sleep 2
docker-compose logs server 2>&1 | grep -i "bootstrap secret" || echo "(wait a few seconds, then run: docker-compose logs server | grep 'bootstrap secret')"
