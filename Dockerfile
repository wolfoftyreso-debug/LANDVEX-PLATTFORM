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

# Application. `integrations` GLÖMDES här: api/main.py, api/dev_server.py
# och två datakällsadaptrar importerar integrations.aamos, så imagen
# kraschade på import. Ett test läser den här filens COPY-rader och
# jämför med vad koden faktiskt importerar — se tests/test_deploy.py.
COPY engine ./engine
COPY api ./api
COPY integrations ./integrations
COPY frontend ./frontend
# Prober och mätverktyg följer med: verified_live kan bara bekräftas där
# nätet är öppet, och det är i driftmiljön det är det.
COPY scripts ./scripts

# Non-root runtime + writable data/log dirs.
RUN useradd --create-home --uid 10001 landvex \
    && mkdir -p /data /var/log/landvex \
    && chown -R landvex:landvex /app /data /var/log/landvex
USER landvex

ENV LANDVEX_DB=/data/landvex.db \
    LANDVEX_AUDIT_LOG=/var/log/landvex/audit.jsonl \
    WEB_CONCURRENCY=2 \
    LANDVEX_PREFLIGHT=warn
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)"

# Preflight FÖRST, sedan servern. En checklista i ett dokument läses en
# gång; en som ligger i startvägen läses varje gång. LANDVEX_PREFLIGHT
# avgör vad ett underkänt resultat kostar: 'strict' vägrar ta trafik,
# 'warn' (standard) startar och lägger skälen överst i loggen. `exec` gör
# att gunicorn får signalerna, inte skalet.
#
# gunicorn manages workers + signals; the uvicorn worker gives ASGI.
CMD ["sh", "-c", "python -m scripts.preflight --gate && exec gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:${LANDVEX_PORT:-8000} --access-logfile - --error-logfile - --timeout 30"]
