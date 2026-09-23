from fastapi import FastAPI

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


@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}
