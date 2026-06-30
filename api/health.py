"""GET https://<domain>/api/health — health check."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI

from vercel_app import health_response

app = FastAPI()


@app.get("/")
async def health() -> dict:
    return health_response()
