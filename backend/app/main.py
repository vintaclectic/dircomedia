from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.config import settings
from app.core.auth import require_owner
from app.api.v1 import content, video, distribution, analytics, projects, settings as settings_api, broadcast


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="DirCo Media OS", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── OWNER-ONLY: every route requires the owner token (Phase 0 lockdown). ──
OWNER = [Depends(require_owner)]

app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"], dependencies=OWNER)
app.include_router(content.router, prefix="/api/v1/content", tags=["content"], dependencies=OWNER)
app.include_router(video.router, prefix="/api/v1/video", tags=["video"], dependencies=OWNER)
app.include_router(distribution.router, prefix="/api/v1/distribution", tags=["distribution"], dependencies=OWNER)
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"], dependencies=OWNER)
app.include_router(settings_api.router, prefix="/api/v1/settings", tags=["settings"], dependencies=OWNER)
app.include_router(broadcast.router, prefix="/api/v1/broadcast", tags=["broadcast"], dependencies=OWNER)


@app.get("/health")
async def health():
    return {"status": "ok"}
