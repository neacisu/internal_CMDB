"""AuthService — user authentication and password management.

Uses argon2-cffi (Argon2id) for password hashing.  passlib is NOT used
because it depends on the stdlib ``crypt`` module which was removed in
Python 3.13 (PEP 594).
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import update
from sqlalchemy.orm import Session

from internalcmdb.auth.models import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Argon2id password hasher — OWASP recommended parameters (April 2026)
# ---------------------------------------------------------------------------

_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# Pre-computed dummy hash for constant-time user-not-found path.
# Must be computed at import time so the first rejection is not slower.
_DUMMY_HASH = _ph.hash("dummy_constant_for_timing_equalization_internalcmdb")


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return an Argon2id hash string for *plain*."""
    return _ph.hash(plain)


def _dummy_verify() -> None:
    """Run a full Argon2id verification to equalise timing when user not found.

    Prevents user-enumeration via response-timing differences.
    """
    with contextlib.suppress(Exception):
        _ph.verify(_DUMMY_HASH, "dummy_constant_for_timing_equalization_internalcmdb")


def _verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*.  Never raises."""
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except VerificationError:
        logger.warning("Argon2 verification error (possible hash corruption)")
        return False
    except Exception:
        logger.exception("Unexpected error during password verification")
        return False


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------


class AuthService:
    """Database-backed authentication operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def authenticate(self, email: str, password: str) -> User | None:
        """Return User on success or None on any failure.

        Always takes constant time — whether the user exists or not.
        Never distinguishes "wrong email" from "wrong password" in the
        return value (anti-enumeration).
        """
        user = self._db.query(User).filter(User.email == email).first()
        if user is None:
            _dummy_verify()  # equalise timing
            return None

        if not _verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return user

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key."""
        return self._db.query(User).filter(User.user_id == user_id).first()

    def update_last_login(self, user_id: uuid.UUID) -> None:
        """Stamp last_login_at = now() for the given user."""
        self._db.execute(
            update(User).where(User.user_id == user_id).values(last_login_at=datetime.now(UTC))
        )
        self._db.commit()

    def reset_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change password after verifying the current one.

        Returns True on success, False if current_password is wrong.
        On success sets force_password_change=False and
        password_changed_at=now().
        """
        user = self._db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            return False

        if not _verify_password(current_password, user.hashed_password):
            return False

        self._db.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                hashed_password=hash_password(new_password),
                password_changed_at=datetime.now(UTC),
                force_password_change=False,
            )
        )
        self._db.commit()
        return True
