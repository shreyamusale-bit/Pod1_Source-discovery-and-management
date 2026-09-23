from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(prefix="/sources", tags=["sources"])


def _get_or_404(db: Session, source_id: str) -> models.Source:
    source = crud.get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.post("/", response_model=schemas.SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(payload: schemas.SourceCreate, db: Session = Depends(get_db)):
    """Submit a new candidate. Always lands as DISCOVERED / PENDING — never live."""
    if crud.get_source_by_address(db, payload.address) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this address already exists",
        )
    return crud.create_source(db, payload)


@router.get("/", response_model=List[schemas.SourceOut])
def list_sources(
    lifecycle_status: Optional[models.LifecycleStatus] = None,
    authorization_status: Optional[models.AuthorizationStatus] = None,
    transport: Optional[models.TransportType] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return crud.list_sources(
        db, lifecycle_status, authorization_status, transport, enabled, skip, limit
    )


@router.get("/{source_id}", response_model=schemas.SourceOut)
def get_source(source_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, source_id)


@router.put("/{source_id}", response_model=schemas.SourceOut)
def update_source(source_id: str, payload: schemas.SourceUpdate, db: Session = Depends(get_db)):
    source = _get_or_404(db, source_id)
    return crud.update_source(db, source, payload)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str, db: Session = Depends(get_db)):
    """
    Hard delete — for cleaning up bad test data only.
    To revoke a real source, transition it to DISABLED instead so past
    evidence stays linked to a record (see PATCH /{id}/lifecycle).
    """
    source = _get_or_404(db, source_id)
    crud.delete_source(db, source)


@router.patch("/{source_id}/authorize", response_model=schemas.SourceOut)
def authorize_source(
    source_id: str, decision: schemas.AuthorizationDecision, db: Session = Depends(get_db)
):
    """The approval gate. Every call records who decided, when, and on what basis."""
    source = _get_or_404(db, source_id)
    if source.authorization_status != models.AuthorizationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source is already {source.authorization_status.value}",
        )
    return crud.decide_authorization(db, source, decision)


@router.patch("/{source_id}/lifecycle", response_model=schemas.SourceOut)
def transition_lifecycle(
    source_id: str, payload: schemas.LifecycleTransition, db: Session = Depends(get_db)
):
    source = _get_or_404(db, source_id)
    allowed = models.ALLOWED_LIFECYCLE_TRANSITIONS.get(source.lifecycle_status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move from {source.lifecycle_status.value} to "
                f"{payload.status.value}. Allowed: "
                f"{[s.value for s in allowed] or 'none — terminal state'}"
            ),
        )
    try:
        return crud.transition_lifecycle(db, source, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{source_id}/health", response_model=schemas.SourceOut)
def report_health(source_id: str, report: schemas.HealthReport, db: Session = Depends(get_db)):
    """Called by the crawler after each fetch attempt against this source."""
    source = _get_or_404(db, source_id)
    return crud.record_health(db, source, report)
