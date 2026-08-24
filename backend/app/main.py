import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.actions import router as actions_router
from app.routers.microsoft import router as microsoft_router
from app.routers.dossiers import router as dossiers_router
from app.routers.companies import router as companies_router

settings = get_settings()

app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)
OUTLOOK_SYNC_INTERVAL_SECONDS = 30 * 60
_outlook_sync_lock = asyncio.Lock()
_outlook_sync_task: asyncio.Task[None] | None = None


async def _outlook_sync_loop() -> None:
    while True:
        await asyncio.sleep(OUTLOOK_SYNC_INTERVAL_SECONDS)
        if _outlook_sync_lock.locked():
            logger.info("Skipping scheduled Outlook contact sync because another sync is active")
            continue
        async with _outlook_sync_lock:
            try:
                from app.services.microsoft_graph import MicrosoftGraphClient
                from app.services.companies import synchronize_linked_outlook_contacts

                await synchronize_linked_outlook_contacts(MicrosoftGraphClient())
            except (ValueError, RuntimeError) as exc:
                logger.warning("Scheduled Outlook contact sync skipped or failed: %s", exc)
            except Exception:
                logger.exception("Scheduled Outlook contact sync failed unexpectedly")


@app.on_event("startup")
async def start_outlook_sync_task() -> None:
    global _outlook_sync_task
    _outlook_sync_task = asyncio.create_task(_outlook_sync_loop())


@app.on_event("shutdown")
async def stop_outlook_sync_task() -> None:
    if _outlook_sync_task is not None:
        _outlook_sync_task.cancel()
        try:
            await _outlook_sync_task
        except asyncio.CancelledError:
            pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.0.145:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello API"}


app.include_router(microsoft_router)
app.include_router(actions_router)
app.include_router(dossiers_router)
app.include_router(companies_router)
