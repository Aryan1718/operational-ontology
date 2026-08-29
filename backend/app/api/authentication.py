"""Signed bearer-token authentication for human API requests."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationFailedError
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)

_JWT_ALGORITHM = "HS256"
_SUPPORTED_HUMAN_ROLES = (
    OntologyRole.VIEWER,
    OntologyRole.PLANNER,
    OntologyRole.OPERATIONS_MANAGER,
    OntologyRole.ADMIN,
)


class HumanApiTokenClaims(BaseModel):
    """Validated JWT claims used to construct a trusted human ActorContext."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    sub: str = Field(min_length=1)
    roles: tuple[OntologyRole, ...] = Field(default_factory=tuple)
    exp: int
    iss: str | None = None
    aud: str | list[str] | None = None
    nbf: int | None = None
    iat: int | None = None
    actor_type_claim: ActorType | None = Field(
        default=None,
        validation_alias=AliasChoices("actorType", "actor_type"),
    )
    invocation_source_claim: InvocationSource | None = Field(
        default=None,
        validation_alias=AliasChoices("invocationSource", "invocation_source"),
    )

    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles(cls, value: object) -> tuple[OntologyRole, ...]:
        if not isinstance(value, list):
            raise ValueError("roles must be a list.")
        roles: list[OntologyRole] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("roles must contain only role strings.")
            try:
                role = OntologyRole(item)
            except ValueError:
                raise ValueError(
                    "roles must contain only known ontology roles."
                ) from None
            if role not in _SUPPORTED_HUMAN_ROLES:
                raise ValueError("roles must contain only supported human API roles.")
            if role in _SUPPORTED_HUMAN_ROLES and role not in roles:
                roles.append(role)
        if not roles:
            raise ValueError("At least one supported human role is required.")
        return tuple(roles)

    @field_validator("actor_type_claim")
    @classmethod
    def validate_actor_type_claim(cls, value: ActorType | None) -> ActorType | None:
        if value is not None and value is not ActorType.HUMAN:
            raise ValueError("Human API tokens cannot assert non-human actor types.")
        return value

    @field_validator("invocation_source_claim")
    @classmethod
    def validate_invocation_source_claim(
        cls,
        value: InvocationSource | None,
    ) -> InvocationSource | None:
        if value is not None and value is not InvocationSource.API:
            raise ValueError(
                "Human API tokens cannot assert non-API invocation sources."
            )
        return value


class _JwtHeader(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    alg: str
    typ: str | None = None


def authenticate_human_api_request(
    *,
    authorization_header: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> ActorContext:
    """Validate the bearer token and return the trusted human API actor."""
    if not settings.api_auth_enabled or not settings.api_jwt_secret:
        raise AuthenticationFailedError()
    token = _extract_bearer_token(authorization_header)
    claims = validate_human_api_token(
        token=token,
        settings=settings,
        now=now,
    )
    return ActorContext(
        actor_id=claims.sub,
        actor_type=ActorType.HUMAN,
        roles=claims.roles,
        invocation_source=InvocationSource.API,
    )


def validate_human_api_token(
    *,
    token: str,
    settings: Settings,
    now: datetime | None = None,
) -> HumanApiTokenClaims:
    """Validate one signed HS256 JWT for the human API surface."""
    if settings.api_jwt_algorithm != _JWT_ALGORITHM or not settings.api_jwt_secret:
        raise AuthenticationFailedError()

    header_segment, payload_segment, signature_segment = _split_token(token)
    try:
        header = _JwtHeader.model_validate_json(_decode_segment(header_segment))
    except ValidationError as exc:
        raise AuthenticationFailedError() from exc
    if header.alg != settings.api_jwt_algorithm:
        raise AuthenticationFailedError()

    expected_signature = _sign(
        message=f"{header_segment}.{payload_segment}".encode("ascii"),
        secret=settings.api_jwt_secret,
    )
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise AuthenticationFailedError()

    try:
        claims = HumanApiTokenClaims.model_validate_json(
            _decode_segment(payload_segment)
        )
    except ValidationError as exc:
        raise AuthenticationFailedError() from exc
    current_timestamp = int((now or datetime.now(UTC)).timestamp())
    if claims.exp < current_timestamp:
        raise AuthenticationFailedError()
    if claims.nbf is not None and claims.nbf > current_timestamp:
        raise AuthenticationFailedError()
    if settings.api_jwt_issuer is not None and claims.iss != settings.api_jwt_issuer:
        raise AuthenticationFailedError()
    if settings.api_jwt_audience is not None and not _matches_audience(
        token_audience=claims.aud,
        expected_audience=settings.api_jwt_audience,
    ):
        raise AuthenticationFailedError()
    return claims


def create_human_api_token(
    *,
    subject: str,
    roles: tuple[OntologyRole, ...],
    settings: Settings,
    expires_at: datetime,
    issued_at: datetime | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a deterministic signed JWT for development and test use."""
    if not settings.api_jwt_secret:
        raise ValueError("API_JWT_SECRET must be configured to create a token.")
    unsupported_roles = tuple(
        role for role in roles if role not in _SUPPORTED_HUMAN_ROLES
    )
    if unsupported_roles:
        raise ValueError("Human API tokens can only be created for human API roles.")
    issued = issued_at or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": [role.value for role in roles],
        "exp": int(expires_at.timestamp()),
        "iat": int(issued.timestamp()),
    }
    if settings.api_jwt_issuer is not None:
        payload["iss"] = settings.api_jwt_issuer
    if settings.api_jwt_audience is not None:
        payload["aud"] = settings.api_jwt_audience
    if extra_claims:
        payload.update(extra_claims)

    header_segment = _encode_segment({"alg": settings.api_jwt_algorithm, "typ": "JWT"})
    payload_segment = _encode_segment(payload)
    signature_segment = _sign(
        message=f"{header_segment}.{payload_segment}".encode("ascii"),
        secret=settings.api_jwt_secret,
    )
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def build_bearer_authorization_header(token: str) -> str:
    """Format one token for the Authorization request header."""
    return f"Bearer {token}"


def main() -> None:
    """Generate a development/test token from configured API JWT settings."""
    parser = argparse.ArgumentParser(description="Create a signed API bearer token.")
    parser.add_argument("--subject", required=True)
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        choices=[role.value for role in _SUPPORTED_HUMAN_ROLES],
        required=True,
    )
    parser.add_argument("--expires-in-seconds", type=int, default=3600)
    arguments = parser.parse_args()
    settings = get_settings()
    token = create_human_api_token(
        subject=arguments.subject,
        roles=tuple(OntologyRole(role) for role in arguments.roles),
        settings=settings,
        expires_at=datetime.now(UTC) + timedelta(seconds=arguments.expires_in_seconds),
    )
    print(token)


def _extract_bearer_token(authorization_header: str | None) -> str:
    if authorization_header is None:
        raise AuthenticationFailedError()
    scheme, _, token = authorization_header.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationFailedError()
    return token.strip()


def _split_token(token: str) -> tuple[str, str, str]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise AuthenticationFailedError()
    return parts[0], parts[1], parts[2]


def _encode_segment(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_segment(segment: str) -> str:
    try:
        padding = "=" * ((4 - len(segment) % 4) % 4)
        decoded = base64.urlsafe_b64decode((segment + padding).encode("ascii"))
        return decoded.decode("utf-8")
    except Exception as exc:  # pragma: no cover - defensive invalid-token branch
        raise AuthenticationFailedError() from exc


def _sign(*, message: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _matches_audience(
    *,
    token_audience: str | list[str] | None,
    expected_audience: str,
) -> bool:
    if token_audience is None:
        return False
    if isinstance(token_audience, str):
        return token_audience == expected_audience
    return expected_audience in token_audience

