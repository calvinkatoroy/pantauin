import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.deps import init_db
from app.api.routes import scan, report, keywords


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.evidence_dir, exist_ok=True)
    yield


app = FastAPI(
    title="Pantauin API",
    description="Indonesian Government & Academic Website Security Scanner",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(keywords.router, prefix="/api")

# Serve evidence screenshots as static files
if os.path.exists(settings.evidence_dir):
    app.mount("/evidence", StaticFiles(directory=settings.evidence_dir), name="evidence")


@app.get("/health")
async def health():
    return {"status": "ok"}
