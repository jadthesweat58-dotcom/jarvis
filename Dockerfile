FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_MODE=cloud \
    JARVIS_DATA_DIR=/data \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jarvis ./jarvis
RUN mkdir -p /data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/healthz')"

# --no-proxy-headers: never trust X-Forwarded-For, so nobody can pretend to be
# "localhost" and skip the access token.
CMD ["sh", "-c", "uvicorn jarvis.server:app --host 0.0.0.0 --port ${PORT} --no-proxy-headers"]
