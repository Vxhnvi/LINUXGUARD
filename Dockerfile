FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    LINUXGUARD_HOST=0.0.0.0 LINUXGUARD_PORT=5000 LINUXGUARD_DB=/app/data/linuxguard.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts

# Run as an unprivileged user; only /app/data is writable.
RUN useradd --system --uid 10001 --no-create-home linuxguard \
    && mkdir -p /app/data && chown linuxguard /app/data \
    && chmod +x scripts/*.sh
USER linuxguard

EXPOSE 5000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "backend.app"]
