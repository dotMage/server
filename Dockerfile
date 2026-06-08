FROM python:3.13-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY main.py .

RUN mkdir -p /app/static
ENV DOTMAGE_STATIC_DIR=/app/static

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
