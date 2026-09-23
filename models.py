"""
The `sources` table — the governed registry itself.

Two state machines live on one row:
  lifecycle_status      DISCOVERED -> VALIDATED -> AUTHORIZED -> ACTIVE
                         (either branch can also land on QUARANTINED / DISABLED)
  authorization_status  PENDING -> APPROVED | REJECTED  (APPROVED can later EXPIRE)

A source only becomes crawlable (lifecycle_status == ACTIVE) once
authorization_status == APPROVED. The API layer enforces that; the
column itself just stores state.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import validates

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, enum.Enum):
    FORUM = "forum"
    MARKETPLACE = "marketplace"
    PASTE_SITE = "paste_site"
    TELEGRAM = "telegram"
    CHAT_CHANNEL = "chat_channel"
    INDEX = "index"
    OTHER = "other"


class TransportType(str, enum.Enum):
    CLEARNET = "clearnet"
    TOR = "tor"
    I2P = "i2p"


class LifecycleStatus(str, enum.Enum):
    DISCOVERED = "discovered"    # just proposed, nothing checked yet
    VALIDATED = "validated"      # address format + reachability checked
    AUTHORIZED = "authorized"    # approved, not yet scheduled
    ACTIVE = "active"            # live in the crawl rotation
    QUARANTINED = "quarantined"  # temporarily pulled (failures, policy hold)
    DISABLED = "disabled"        # revoked — terminal, past evidence untouched


class AuthorizationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Lifecycle transitions the API will allow. Anything not listed here is refused.
ALLOWED_LIFECYCLE_TRANSITIONS = {
    LifecycleStatus.DISCOVERED: {LifecycleStatus.VALIDATED, LifecycleStatus.DISABLED},
    LifecycleStatus.VALIDATED: {LifecycleStatus.AUTHORIZED, LifecycleStatus.DISABLED},
    LifecycleStatus.AUTHORIZED: {LifecycleStatus.ACTIVE, LifecycleStatus.DISABLED},
    LifecycleStatus.ACTIVE: {LifecycleStatus.QUARANTINED, LifecycleStatus.DISABLED},
    LifecycleStatus.QUARANTINED: {LifecycleStatus.ACTIVE, LifecycleStatus.DISABLED},
    LifecycleStatus.DISABLED: set(),  # terminal — revocation is not reversible here
}


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=_uuid)

    # --- identity ---
    name = Column(String, nullable=False)
    address = Column(String, nullable=False, unique=True, index=True)
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.OTHER)
    transport = Column(Enum(TransportType), nullable=False)

    # --- discovery provenance ---
    discovered_by = Column(String, nullable=True)     # analyst / system that proposed it
    discovered_from = Column(String, nullable=True)    # e.g. "link on source <id>"

    # --- lifecycle ---
    lifecycle_status = Column(
        Enum(LifecycleStatus), nullable=False, default=LifecycleStatus.DISCOVERED
    )

    # --- authorization / governance ---
    authorization_status = Column(
        Enum(AuthorizationStatus), nullable=False, default=AuthorizationStatus.PENDING
    )
    authorized_by = Column(String, nullable=True)
    authorized_at = Column(DateTime, nullable=True)
    authorization_basis = Column(Text, nullable=True)  # legal/policy justification
    review_due = Column(DateTime, nullable=True)        # re-review / expiry date

    # --- crawl policy ---
    rate_limit_seconds = Column(Integer, nullable=False, default=30)
    max_depth = Column(Integer, nullable=False, default=1)
    allowed_paths = Column(Text, nullable=True)  # comma-separated path prefixes

    # --- health monitoring ---
    enabled = Column(Boolean, nullable=False, default=True)
    last_fetch_at = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_content_hash = Column(String, nullable=True)

    # --- scoring ---
    trust_weight = Column(Integer, nullable=False, default=50)  # 0-100

    # --- bookkeeping ---
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    @validates("trust_weight")
    def _validate_trust_weight(self, key, value):
        if not 0 <= value <= 100:
            raise ValueError("trust_weight must be between 0 and 100")
        return value
