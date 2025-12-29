from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amex_core.logging import configure_logging
from amex_core.settings import settings
from apps.api.routers import chat, data, tools

app = FastAPI(title="Amex Agentic Chatbot API", version="0.1.0")

# CORS (tighten in prod!)
origins = [o.strip() for o in settings.API_CORS_ORIGINS.split(",")] if settings.API_CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


app.include_router(chat.router)
app.include_router(data.router)
app.include_router(tools.router)


def run() -> None:
    configure_logging()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # turn off in real prod
    )


if __name__ == "__main__":
    run()
