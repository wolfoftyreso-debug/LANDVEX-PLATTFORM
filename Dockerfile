# LANDVEX Opportunity Engine — production image.
# The engine core is dependency-free; only the API layer needs requirements.
# Runs as a non-root user under gunicorn + uvicorn workers.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANDVEX_PORT=8000

WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application.
COPY engine ./engine
COPY api ./api
COPY frontend ./frontend

# Non-root runtime + writable data/log dirs.
RUN useradd --create-home --uid 10001 landvex \
    && mkdir -p /data /var/log/landvex \
    && chown -R landvex:landvex /app /data /var/log/landvex
USER landvex

ENV LANDVEX_DB=/data/landvex.db \
    LANDVEX_AUDIT_LOG=/var/log/landvex/audit.jsonl \
    WEB_CONCURRENCY=2
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)"

# gunicorn manages workers + signals; the uvicorn worker gives ASGI.
CMD ["sh", "-c", "gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${LANDVEX_PORT:-8000} --access-logfile - --error-logfile - --timeout 30"]
