from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_source(db: Session, payload: schemas.SourceCreate) -> models.Source:
    source = models.Source(
        name=payload.name,
        address=payload.address,
        source_type=payload.source_type,
        transport=payload.transport,
        discovered_by=payload.discovered_by,
        discovered_from=payload.discovered_from,
        rate_limit_seconds=payload.rate_limit_seconds,
        max_depth=payload.max_depth,
        allowed_paths=payload.allowed_paths,
        # every new candidate starts at the bottom of both state machines
        lifecycle_status=models.LifecycleStatus.DISCOVERED,
        authorization_status=models.AuthorizationStatus.PENDING,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def get_source(db: Session, source_id: str) -> Optional[models.Source]:
    return db.query(models.Source).filter(models.Source.id == source_id).first()


def get_source_by_address(db: Session, address: str) -> Optional[models.Source]:
    return db.query(models.Source).filter(models.Source.address == address).first()


def list_sources(
    db: Session,
    lifecycle_status: Optional[models.LifecycleStatus] = None,
    authorization_status: Optional[models.AuthorizationStatus] = None,
    transport: Optional[models.TransportType] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(models.Source)
    if lifecycle_status is not None:
        q = q.filter(models.Source.lifecycle_status == lifecycle_status)
    if authorization_status is not None:
        q = q.filter(models.Source.authorization_status == authorization_status)
    if transport is not None:
        q = q.filter(models.Source.transport == transport)
    if enabled is not None:
        q = q.filter(models.Source.enabled == enabled)
    return q.order_by(models.Source.created_at.desc()).offset(skip).limit(limit).all()


def update_source(
    db: Session, source: models.Source, payload: schemas.SourceUpdate
) -> models.Source:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


def delete_source(db: Session, source: models.Source) -> None:
    db.delete(source)
    db.commit()


def decide_authorization(
    db: Session, source: models.Source, decision: schemas.AuthorizationDecision
) -> models.Source:
    source.authorization_status = decision.decision
    source.authorized_by = decision.decided_by
    source.authorized_at = _utcnow()
    source.authorization_basis = decision.basis
    source.review_due = decision.review_due

    # Approval alone does not make a source ACTIVE — it only clears the
    # gate. The lifecycle still has to be walked forward explicitly via
    # PATCH /sources/{id}/lifecycle. Rejection does end the lifecycle.
    if decision.decision == models.AuthorizationStatus.REJECTED:
        source.lifecycle_status = models.LifecycleStatus.DISABLED

    db.commit()
    db.refresh(source)
    return source


def transition_lifecycle(
    db: Session, source: models.Source, new_status: models.LifecycleStatus
) -> models.Source:
    # Moving to ACTIVE requires a live approval — this is the one place
    # the two state machines are cross-checked.
    if new_status == models.LifecycleStatus.ACTIVE and (
        source.authorization_status != models.AuthorizationStatus.APPROVED
    ):
        raise ValueError("Source must be APPROVED before it can go ACTIVE")

    source.lifecycle_status = new_status
    db.commit()
    db.refresh(source)
    return source


def record_health(
    db: Session, source: models.Source, report: schemas.HealthReport
) -> models.Source:
    source.last_fetch_at = _utcnow()
    if report.success:
        source.consecutive_failures = 0
        if report.content_hash:
            source.last_content_hash = report.content_hash
    else:
        source.consecutive_failures += 1
        # three strikes -> auto-quarantine, never auto-disable
        if (
            source.consecutive_failures >= 3
            and source.lifecycle_status == models.LifecycleStatus.ACTIVE
        ):
            source.lifecycle_status = models.LifecycleStatus.QUARANTINED
    db.commit()
    db.refresh(source)
    return source
