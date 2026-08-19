from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.actions import router as actions_router
from app.routers.microsoft import router as microsoft_router
from app.routers.dossiers import router as dossiers_router

settings = get_settings()

app = FastAPI(title=settings.app_name)

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
