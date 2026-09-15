"""FastAPI 入口：CORS + 路由 + 生命周期。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, history
from .web_config import close_database

app = FastAPI(title="Procurement Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(history.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.on_event("shutdown")
async def _shutdown() -> None:
    close_database()
