import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as main_router
from app.api.webhooks import router as webhook_router
from app.models.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Pipeline Optimizer", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(main_router)
app.include_router(webhook_router)


@app.on_event("startup")
def startup():
    init_db()
