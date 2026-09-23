"""
Address-format validation, kept separate from the Pydantic schemas so it can
be unit-tested and reused (e.g. by a future discovery worker) on its own.
"""
import re

from .models import TransportType

# Onion v3 addresses: 56-char base32 + ".onion"
_ONION_V3_RE = re.compile(r"^[a-z2-7]{56}\.onion$", re.IGNORECASE)

# I2P .b32.i2p addresses: 52-char base32 + ".b32.i2p"
_I2P_B32_RE = re.compile(r"^[a-z2-7]{52}\.b32\.i2p$", re.IGNORECASE)

_CLEARNET_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


class AddressValidationError(ValueError):
    pass


def validate_address(address: str, transport: TransportType) -> None:
    """Raise AddressValidationError if `address` doesn't match `transport`."""
    address = address.strip()

    if transport == TransportType.TOR:
        host = address.replace("http://", "").replace("https://", "").rstrip("/")
        if not _ONION_V3_RE.match(host):
            raise AddressValidationError(
                "Tor sources must be a 56-character v3 .onion address"
            )
    elif transport == TransportType.I2P:
        host = address.replace("http://", "").replace("https://", "").rstrip("/")
        if not _I2P_B32_RE.match(host):
            raise AddressValidationError(
                "I2P sources must be a 52-character .b32.i2p address"
            )
    elif transport == TransportType.CLEARNET:
        if not _CLEARNET_RE.match(address):
            raise AddressValidationError(
                "Clearnet sources must be a valid http:// or https:// URL"
            )
    else:  # pragma: no cover - guarded by the enum, kept for safety
        raise AddressValidationError(f"Unknown transport type: {transport}")
