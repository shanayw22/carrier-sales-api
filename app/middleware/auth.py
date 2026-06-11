from fastapi import HTTPException, Request

from app.config import API_KEY


async def verify_api_key(request: Request):
    if request.url.path in {"/", "/health"} or request.url.path.startswith("/dashboard"):
        return

    key = request.headers.get("X-API-Key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")