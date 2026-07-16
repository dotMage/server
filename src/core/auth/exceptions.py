"""Domain exception hierarchy."""

from __future__ import annotations


class DotMageError(Exception):
    """Base exception for all domain errors."""

    status_code: int = 500
    message: str = "Internal error"


# --- Auth ---


class NotAuthenticatedError(DotMageError):
    status_code = 401
    message = "Missing or invalid Authorization header"


class InvalidTokenError(DotMageError):
    status_code = 401
    message = "Invalid token"


class DeviceRevokedError(DotMageError):
    status_code = 401
    message = "Device has been revoked"


class TokenExpiredError(DotMageError):
    status_code = 401
    message = "Token has expired"


class EnrollmentTokenRequiredError(DotMageError):
    status_code = 401
    message = "Enrollment token required"


class InvalidEnrollmentTokenError(DotMageError):
    status_code = 401
    message = "Invalid enrollment token"


class EnrollmentTokenRevokedError(DotMageError):
    status_code = 401
    message = "Enrollment token has been revoked"


class EnrollmentTokenExpiredError(DotMageError):
    status_code = 401
    message = "Enrollment token has expired"


class InvalidRefreshTokenError(DotMageError):
    status_code = 401
    message = "Invalid refresh token"


# --- Account ---


class AccountExistsError(DotMageError):
    status_code = 409
    message = "Account already initialized"


class InvalidBootstrapError(DotMageError):
    status_code = 403
    message = "Invalid bootstrap secret"


class AccountNotFoundError(DotMageError):
    status_code = 404
    message = "Account not initialized"


class UnauthorizedError(DotMageError):
    status_code = 401
    message = "Valid token required"


# --- App ---


class AppExistsError(DotMageError):
    status_code = 409

    def __init__(self, name: str) -> None:
        self.message = f"App '{name}' already exists"


class AppNotFoundError(DotMageError):
    status_code = 404

    def __init__(self, name: str) -> None:
        self.message = f"App '{name}' not found"


# --- Environment ---


class EnvExistsError(DotMageError):
    status_code = 409

    def __init__(self, name: str) -> None:
        self.message = f"Environment '{name}' already exists"


class EnvNotFoundError(DotMageError):
    status_code = 404

    def __init__(self, name: str) -> None:
        self.message = f"Environment '{name}' not found"


class CopyFromUnsupportedError(DotMageError):
    """Old clients ask the server to copy a blob into a new environment.

    An E2E server can't do that: ciphertext is AEAD-bound to app|env|rev, so a
    byte-copy produces a revision that fails authentication on every pull.
    """

    status_code = 400
    message = (
        "copy_from is not supported: the server cannot copy encrypted blobs "
        "between environments (ciphertext is bound to app|env|rev). "
        "Upgrade the CLI — newer versions copy client-side: dmage upgrade"
    )


# --- Revision ---


class RevisionConflictError(DotMageError):
    status_code = 409

    def __init__(self, server_rev: int, parent_rev: int) -> None:
        self.message = (
            f"Remote is ahead (server rev {server_rev}, your parent {parent_rev})"
        )


class BadRevisionError(DotMageError):
    status_code = 400

    def __init__(self, rev: str) -> None:
        self.message = f"Invalid revision: {rev}"


class RevisionNotFoundError(DotMageError):
    status_code = 404

    def __init__(self, rev: int | str = 0) -> None:
        if rev == 0:
            self.message = "No revisions"
        else:
            self.message = f"Revision {rev} not found"


class AppOrEnvNotFoundError(DotMageError):
    status_code = 404
    message = "App or environment not found"


# --- Rotation (spec L) ---


class RotationInProgressError(DotMageError):
    status_code = 409
    message = "Key rotation in progress — retry after it completes"


class RotationConflictError(DotMageError):
    status_code = 409

    def __init__(self, detail: str) -> None:
        self.message = f"Rotation conflict: {detail}"


class RotationNotActiveError(DotMageError):
    status_code = 405
    message = "Blob replacement is only allowed during key rotation"


class RotationIncompleteError(DotMageError):
    status_code = 409

    def __init__(self, stale: int) -> None:
        self.message = f"Rotation incomplete: {stale} revision(s) still on the old key"


# --- Device ---


class DeviceNotFoundError(DotMageError):
    status_code = 404
    message = "Device not found"


class DeviceScopeError(DotMageError):
    status_code = 403
    message = "This token is scoped to a different app/environment"


# --- Team (spec K/B.9) ---


class TeamModeRequiredError(DotMageError):
    status_code = 404
    message = "Not found"  # solo servers do not reveal team endpoints


class NotAnOwnerError(DotMageError):
    status_code = 403
    message = "This action requires the owner role"


class RoleForbiddenError(DotMageError):
    status_code = 403
    message = "Your role does not allow this action"


class UserExistsError(DotMageError):
    status_code = 409

    def __init__(self, name: str) -> None:
        self.message = f"User '{name}' already exists"


class InvitationInvalidError(DotMageError):
    status_code = 404
    message = "Invitation not found, expired or already used"


class UserNotFoundError(DotMageError):
    status_code = 404
    message = "User not found"


class LastOwnerError(DotMageError):
    status_code = 409
    message = "Cannot demote or remove the last owner"


# --- Rate limit ---


class RateLimitedError(DotMageError):
    status_code = 429
    message = "Too many requests, try again later"
