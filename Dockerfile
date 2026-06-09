FROM python:3.13-slim

LABEL org.opencontainers.image.source=https://github.com/dotMage/dotmage-server

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY main.py .

# Web admin static files (populated by CI or build.sh)
RUN mkdir -p /app/static
COPY static/ /app/static/
ENV DOTMAGE_STATIC_DIR=/app/static

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
