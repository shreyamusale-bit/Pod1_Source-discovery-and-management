from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models
from .database import Base, engine
from .routers import sources

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CyArt Source Registry",
    description=(
        "Source Management module for the Dark Web Monitoring & Threat "
        "Intelligence Platform prototype. Tracks every crawl target as a "
        "governed record: identity, transport, authorization, crawl "
        "policy, and health — instead of a hardcoded list."
    ),
    version="0.1.0",
)

app.include_router(sources.router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def dashboard():
    """Serves the source registry dashboard."""
    return FileResponse(STATIC_DIR / "index.html")


# Any other static assets (css/js/images) added later under app/static/
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
