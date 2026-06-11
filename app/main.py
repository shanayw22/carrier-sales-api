from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from app.database import Base, engine
from app.middleware.auth import verify_api_key
from app.routes import carriers, loads, metrics, webhook


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Carrier Sales API",
    description="API for Inbound Carrier Sales workflow metrics and data",
    version="1.0.0",
    dependencies=[Depends(verify_api_key)],
)

app.include_router(carriers.router)
app.include_router(loads.router)
app.include_router(webhook.router)
app.include_router(metrics.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard/", status_code=307)


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
async def dashboard():
    return FileResponse(Path("dashboard/index.html"))


@app.get("/health")
async def health():
    return {"status": "healthy"}