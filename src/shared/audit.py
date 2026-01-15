"""Security audit logging module.

Provides structured audit logging for security-sensitive events such as
authentication attempts, password changes, and permission changes.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

# Dedicated security audit logger
audit_logger = logging.getLogger("security.audit")


class AuditEvent:
    """Standard audit event types."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    REGISTER_SUCCESS = "register_success"
    REGISTER_FAILED = "register_failed"

    # Token events
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    TOKEN_REVOKED = "token_revoked"

    # Password events
    PASSWORD_CHANGE_SUCCESS = "password_change_success"
    PASSWORD_CHANGE_FAILED = "password_change_failed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    PASSWORD_RESET_FAILED = "password_reset_failed"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Access control events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FORBIDDEN_ACCESS = "forbidden_access"


def audit_log(
    event: str,
    user_id: UUID | str | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a security audit event.

    Args:
        event: Event type from AuditEvent class
        user_id: User ID involved in the event (if known)
        email: Email address involved (masked in logs)
        ip_address: Client IP address
        user_agent: Client user agent string
        success: Whether the operation succeeded
        reason: Reason for failure (if applicable)
        details: Additional event-specific details

    Example:
        audit_log(
            AuditEvent.LOGIN_FAILED,
            email="user@example.com",
            ip_address="192.168.1.1",
            reason="invalid_password",
        )
    """
    # Build audit record
    record = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
    }

    # Add optional fields
    if user_id:
        record["user_id"] = str(user_id)

    if email:
        # Mask email for privacy but keep enough for identification
        record["email"] = _mask_email(email)

    if ip_address:
        record["ip_address"] = ip_address

    if user_agent:
        # Truncate long user agents
        record["user_agent"] = user_agent[:200] if len(user_agent) > 200 else user_agent

    if reason:
        record["reason"] = reason

    if details:
        # Filter out sensitive fields from details
        record["details"] = _sanitize_details(details)

    # Log at appropriate level
    if success:
        audit_logger.info(f"AUDIT: {event}", extra=record)
    else:
        audit_logger.warning(f"AUDIT: {event} - FAILED", extra=record)


def _mask_email(email: str) -> str:
    """Mask email address for privacy.

    Args:
        email: Full email address

    Returns:
        Masked email (e.g., "u***r@example.com")
    """
    if "@" not in email:
        return "***"

    local, domain = email.rsplit("@", 1)

    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]

    return f"{masked_local}@{domain}"


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from details.

    Args:
        details: Original details dict

    Returns:
        Sanitized details with sensitive fields removed
    """
    sensitive_fields = {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "reset_token",
        "secret",
        "api_key",
        "authorization",
    }

    return {
        k: "[REDACTED]" if k.lower() in sensitive_fields else v
        for k, v in details.items()
    }


def configure_audit_logging(log_file: str | None = None) -> None:
    """Configure the audit logger.

    Args:
        log_file: Optional file path for audit logs.
                  If None, logs go to the default handler.

    Call this during application startup to ensure audit logs
    are properly captured.
    """
    audit_logger.setLevel(logging.INFO)

    # Create formatter for audit logs
    formatter = logging.Formatter(
        "%(asctime)s - SECURITY_AUDIT - %(levelname)s - %(message)s - %(extra_data)s"
    )

    if log_file:
        # Add file handler for audit logs
        handler = logging.FileHandler(log_file)
        handler.setFormatter(formatter)
        audit_logger.addHandler(handler)
