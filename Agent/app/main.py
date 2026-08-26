from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.logging_config import configure_logging

configure_logging()

app = FastAPI(title="max-agent")
app.include_router(health_router)
app.include_router(chat_router)
