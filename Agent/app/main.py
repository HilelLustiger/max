import logging

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="max-agent")
app.include_router(health_router)
app.include_router(chat_router)
