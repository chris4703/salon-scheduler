FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    SALON_DB=/app/data/salon.sqlite3

WORKDIR /app
RUN groupadd --gid 10001 salon \
    && useradd --uid 10001 --gid salon --no-create-home salon \
    && mkdir /app/data \
    && chown salon:salon /app/data

COPY --chown=salon:salon server.py ./
COPY --chown=salon:salon public/ ./public/
COPY --chown=salon:salon scripts/ ./scripts/

USER salon
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/state', timeout=3).close()"
CMD ["python", "server.py"]
