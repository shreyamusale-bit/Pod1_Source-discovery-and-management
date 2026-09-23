from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import AuthorizationStatus, LifecycleStatus, SourceType, TransportType
from .validators import AddressValidationError, validate_address


class SourceCreate(BaseModel):
    """What a discovery channel (or an analyst) submits as a new candidate."""

    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., min_length=3, max_length=500)
    source_type: SourceType = SourceType.OTHER
    transport: TransportType
    discovered_by: Optional[str] = None
    discovered_from: Optional[str] = None
    rate_limit_seconds: int = Field(30, ge=1, le=3600)
    max_depth: int = Field(1, ge=0, le=10)
    allowed_paths: Optional[str] = None

    # model_validator (not field_validator) on purpose: field order in a
    # Pydantic v2 model decides validation order, so a field_validator on
    # "address" can run before "transport" is available. This runs after
    # every field is validated, so both are guaranteed to be present.
    @model_validator(mode="after")
    def _address_matches_transport(self):
        try:
            validate_address(self.address, self.transport)
        except AddressValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class SourceUpdate(BaseModel):
    """Editable fields that don't touch lifecycle or authorization state."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    rate_limit_seconds: Optional[int] = Field(None, ge=1, le=3600)
    max_depth: Optional[int] = Field(None, ge=0, le=10)
    allowed_paths: Optional[str] = None
    trust_weight: Optional[int] = Field(None, ge=0, le=100)
    enabled: Optional[bool] = None


class AuthorizationDecision(BaseModel):
    """Body for PATCH /sources/{id}/authorize"""

    decision: AuthorizationStatus  # APPROVED or REJECTED
    decided_by: str = Field(..., min_length=1)
    basis: str = Field(..., min_length=1, description="Legal/policy justification")
    review_due: Optional[datetime] = None

    @field_validator("decision")
    @classmethod
    def _decision_must_be_terminal(cls, v: AuthorizationStatus):
        if v not in (AuthorizationStatus.APPROVED, AuthorizationStatus.REJECTED):
            raise ValueError("decision must be 'approved' or 'rejected'")
        return v


class LifecycleTransition(BaseModel):
    """Body for PATCH /sources/{id}/lifecycle"""

    status: LifecycleStatus


class HealthReport(BaseModel):
    """Body for PATCH /sources/{id}/health — recorded after each crawl attempt."""

    success: bool
    content_hash: Optional[str] = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    source_type: SourceType
    transport: TransportType
    discovered_by: Optional[str]
    discovered_from: Optional[str]
    lifecycle_status: LifecycleStatus
    authorization_status: AuthorizationStatus
    authorized_by: Optional[str]
    authorized_at: Optional[datetime]
    authorization_basis: Optional[str]
    review_due: Optional[datetime]
    rate_limit_seconds: int
    max_depth: int
    allowed_paths: Optional[str]
    enabled: bool
    last_fetch_at: Optional[datetime]
    consecutive_failures: int
    last_content_hash: Optional[str]
    trust_weight: int
    created_at: datetime
    updated_at: datetime
