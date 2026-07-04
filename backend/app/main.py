from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.v1 import content, video, distribution, analytics, projects, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="DirCo Media OS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://172.25.39.140:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(content.router, prefix="/api/v1/content", tags=["content"])
app.include_router(video.router, prefix="/api/v1/video", tags=["video"])
app.include_router(distribution.router, prefix="/api/v1/distribution", tags=["distribution"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])


@app.get("/health")
async def health():
    return {"status": "ok"}
