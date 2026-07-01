import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.broker.ticker_service import bootstrap_live_ticker, ticker_watchdog
from app.routers import accounts, auth, charts, instruments, strategies, ticks, ws
from app.routers.ws import start_relay, stop_relay
from app.scheduler import ensure_global_state, setup_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_global_state()
    await start_relay()
    await bootstrap_live_ticker()
    watchdog = asyncio.create_task(ticker_watchdog())
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("ScalpDesk API started")
    yield
    watchdog.cancel()
    try:
        await watchdog
    except asyncio.CancelledError:
        pass
    scheduler.shutdown()
    await stop_relay()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ScalpDesk", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(instruments.router)
    app.include_router(charts.router)
    app.include_router(strategies.router)
    app.include_router(ticks.router)
    app.include_router(ws.router)
    app.get("/health")(lambda: {"status": "ok"})
    return app


app = create_app()
