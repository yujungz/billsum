import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import AppConfig
from app.database import init_pool, close_pool
from app.api import transfer, query, statistics, settings_api, system, finance, conduction

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = AppConfig.load()
    try:
        await init_pool(config)
    except Exception as e:
        log.warning(f"Database connection failed on startup: {e}. Will retry on first request.")
    yield
    await close_pool()


app = FastAPI(title="BillSum API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transfer.router)
app.include_router(query.router)
app.include_router(statistics.router)
app.include_router(settings_api.router)
app.include_router(system.router)
app.include_router(finance.router)
app.include_router(conduction.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
