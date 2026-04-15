import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.deps import init_db
from app.core.auth import verify_api_key
from app.core.limiter import limiter
from app.core.storage import get_evidence_url
from app.api.routes import scan, report, keywords, schedules, audit, dashboard, auth


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
app.include_router(audit.router, prefix="/api", dependencies=_auth)
app.include_router(dashboard.router, prefix="/api", dependencies=_auth)
# Auth routes have NO global auth dependency - login/setup must be public
app.include_router(auth.router, prefix="/api")

# Evidence serving: redirect to S3/R2 presigned URL when configured,
# otherwise serve as static files from the local evidence directory.
@app.get("/evidence/{scan_id}/{filename}", include_in_schema=False)
async def serve_evidence(scan_id: str, filename: str):
    object_key = f"{scan_id}/{filename}"
    url = get_evidence_url(object_key)
    if url:
        return RedirectResponse(url=url)
    # Fall through to static files below (or 404 if local file missing)
    from fastapi import HTTPException
    local_path = os.path.join(settings.evidence_dir, scan_id, filename)
    if not os.path.exists(local_path):
        raise HTTPException(status_code=404, detail="Evidence file not found")
    from fastapi.responses import FileResponse
    return FileResponse(local_path, media_type="image/png")


@app.get("/health")
async def health():
    return {"status": "ok"}
