from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.redis import close_redis, init_redis
from app.core.storage import init_buckets

from app.features.auth.router import router as auth_router
from app.features.users.router import router as users_router
from app.features.contacts.router import router as contacts_router
from app.features.chats.router import router as chats_router
from app.features.messages.router import router as messages_router
from app.features.realtime.router import router as realtime_router

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

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

app.include_router(users_router, prefix="/api/v1/users", tags=["users"])

app.include_router(contacts_router, prefix="/api/v1/contacts", tags=["contacts"])

app.include_router(chats_router, prefix="/api/v1/chats", tags=["chats"])

app.include_router(messages_router, prefix="/api/v1/chats", tags=["messages"])

app.include_router(realtime_router, tags=["realtime"])


@app.get("/health")
async def health():
    return {"status": "ok"}
