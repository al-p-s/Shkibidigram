from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.redis import close_redis, init_redis
from app.core.storage import init_buckets


@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_redis()
    init_buckets()

    yield

    await close_redis()


app = FastAPI(
    title="Shkibidigram",
    version="1.0.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers — по мере реализации фич
# from app.features.auth.router import router as auth_router
# app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/health")
async def health():
    return {"status": "ok"}
