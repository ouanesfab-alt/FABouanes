FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN groupadd -r fabouanes && useradd -r -g fabouanes -m fabouanes

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /home/fabouanes/FABOuanes && \
    chown -R fabouanes:fabouanes /app /home/fabouanes/FABOuanes

USER fabouanes

ENV FAB_DATA_DIR=/home/fabouanes/FABOuanes \
    WEB_CONCURRENCY=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-", "app.main:app"]
