# LANDVEX Opportunity Engine – container för ECS Fargate/valfri runtime.
# Kärnan är beroendefri; endast API-lagret behöver requirements.txt.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
COPY api ./api
COPY frontend ./frontend

ENV LANDVEX_DB=/data/landvex.db
VOLUME /data
EXPOSE 8000

HEALTHCHECK CMD python -c "import urllib.request; \
    urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
