import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.deps import init_db
from app.core.auth import verify_api_key
from app.core.limiter import limiter
from app.api.routes import scan, report, keywords, schedules


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.evidence_dir, exist_ok=True)
    yield


app = FastAPI(
    title="PantauInd API",
    description="Indonesian Government & Academic Website Security Scanner",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_api_key)]
app.include_router(scan.router, prefix="/api", dependencies=_auth)
app.include_router(report.router, prefix="/api", dependencies=_auth)
app.include_router(keywords.router, prefix="/api", dependencies=_auth)
app.include_router(schedules.router, prefix="/api", dependencies=_auth)

# Serve evidence screenshots as static files
if os.path.exists(settings.evidence_dir):
    app.mount("/evidence", StaticFiles(directory=settings.evidence_dir), name="evidence")


@app.get("/health")
async def health():
    return {"status": "ok"}
