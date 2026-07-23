"""AWS Lambda-ingång: API Gateway → Mangum → FastAPI-appen.

Deployas som funktionshandler `api.lambda_handler.handler`.
Kräver requirements.txt (mangum ingår). Miljövariabler i Lambda:
LANDVEX_API_KEYS, LANDVEX_PG_DSN (eller LANDVEX_DB=/tmp/landvex.db),
LANDVEX_AUDIT_LOG (CloudWatch tar stdout-loggen ändå).
Se infra/aws-notes.md för hela blueprinten.
"""
from mangum import Mangum

from api.main import app

handler = Mangum(app)
