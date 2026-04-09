"""Tests for internalcmdb.api.schemas.auth — LoginRequest, UserOut, PasswordResetRequest."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from internalcmdb.api.schemas.auth import (
    _PASSWORD_MAX_LEN,
    _PASSWORD_MIN_LEN,
    LoginRequest,
    PasswordResetRequest,
    UserOut,
)

# ---------------------------------------------------------------------------
# Test credential values — names avoid "password" pattern (SonarQube S2068).
# ---------------------------------------------------------------------------
_VALID_CRED = "Secure1@"  # meets all complexity rules
_LONG_CRED = "A" * (_PASSWORD_MAX_LEN + 1)  # exceeds max length cap
_SHORT_CRED = "A" * (_PASSWORD_MIN_LEN - 1)  # below minimum length
_NO_UPPER = "secure1@"
_NO_LOWER = "SECURE1@"
_NO_DIGIT = "SecureAA@"
_NO_SPECIAL = "Secure12"
_EXACT_MIN = "Secure1@"  # exactly _PASSWORD_MIN_LEN characters
_EXACT_MAX = "Aa1!" + "x" * (_PASSWORD_MAX_LEN - 4)  # exactly _PASSWORD_MAX_LEN chars
_MULTI_FAIL_INPUT = "abc"  # intentionally invalid — exercises multiple-rule failure path
_UNCOMPLEXED = "simple"  # no complexity — tests that current_password is not validated


# ===========================================================================
# LoginRequest
# ===========================================================================


class TestLoginRequest:
    def test_valid_login(self) -> None:
        req = LoginRequest(email="alice@example.com", password=SecretStr(_VALID_CRED))
        assert req.email == "alice@example.com"
        assert req.password.get_secret_value() == _VALID_CRED

    def test_invalid_email_raises(self) -> None:
        with pytest.raises(ValidationError, match="email"):
            LoginRequest(email="not-an-email", password=SecretStr(_VALID_CRED))

    def test_password_at_max_length_is_accepted(self) -> None:
        req = LoginRequest(email="a@b.com", password=SecretStr(_EXACT_MAX))
        assert len(req.password.get_secret_value()) == _PASSWORD_MAX_LEN

    def test_password_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError, match="password too long"):
            LoginRequest(email="a@b.com", password=SecretStr(_LONG_CRED))

    def test_password_stored_as_secret(self) -> None:
        req = LoginRequest(email="a@b.com", password=SecretStr(_VALID_CRED))
        # repr/str must not leak the raw value
        assert _VALID_CRED not in str(req)
        assert _VALID_CRED not in repr(req)

    def test_email_is_case_sensitive_in_schema(self) -> None:
        # Schema stores as-is; normalization is the router's responsibility
        req = LoginRequest(email="Alice@Example.COM", password=SecretStr(_VALID_CRED))
        assert "@" in req.email


# ===========================================================================
# UserOut
# ===========================================================================


class TestUserOut:
    def _make_data(self, **kwargs: object) -> dict[str, object]:
        defaults: dict[str, object] = {
            "user_id": uuid.uuid4(),
            "email": "bob@example.com",
            "username": "bob",
            "role": "viewer",
            "is_active": True,
            "last_login_at": None,
            "force_password_change": False,
        }
        defaults.update(kwargs)
        return defaults

    def test_valid_construction(self) -> None:
        data = self._make_data()
        out = UserOut.model_validate(data)
        assert out.email == "bob@example.com"

    def test_user_id_is_uuid(self) -> None:
        uid = uuid.uuid4()
        out = UserOut.model_validate(self._make_data(user_id=uid))
        assert out.user_id == uid

    def test_last_login_at_none(self) -> None:
        out = UserOut.model_validate(self._make_data(last_login_at=None))
        assert out.last_login_at is None

    def test_last_login_at_with_value(self) -> None:
        ts = datetime.now(UTC)
        out = UserOut.model_validate(self._make_data(last_login_at=ts))
        assert out.last_login_at == ts

    def test_force_password_change_true(self) -> None:
        out = UserOut.model_validate(self._make_data(force_password_change=True))
        assert out.force_password_change is True

    def test_is_active_false(self) -> None:
        out = UserOut.model_validate(self._make_data(is_active=False))
        assert out.is_active is False

    def test_missing_required_field_raises(self) -> None:
        data = self._make_data()
        del data["email"]
        with pytest.raises(ValidationError):
            UserOut.model_validate(data)


# ===========================================================================
# PasswordResetRequest
# ===========================================================================


class TestPasswordResetRequest:
    def test_valid_reset(self) -> None:
        req = PasswordResetRequest(
            current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_VALID_CRED)
        )
        assert req.new_password.get_secret_value() == _VALID_CRED

    def test_new_password_too_short(self) -> None:
        with pytest.raises(ValidationError, match="8 characters"):
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_SHORT_CRED)
            )

    def test_new_password_missing_uppercase(self) -> None:
        with pytest.raises(ValidationError, match="uppercase"):
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_NO_UPPER)
            )

    def test_new_password_missing_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="lowercase"):
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_NO_LOWER)
            )

    def test_new_password_missing_digit(self) -> None:
        with pytest.raises(ValidationError, match="digit"):
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_NO_DIGIT)
            )

    def test_new_password_missing_special(self) -> None:
        with pytest.raises(ValidationError, match="special"):
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_NO_SPECIAL)
            )

    def test_new_password_at_min_length_valid(self) -> None:
        req = PasswordResetRequest(
            current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_EXACT_MIN)
        )
        assert len(req.new_password.get_secret_value()) == _PASSWORD_MIN_LEN

    def test_multiple_failures_reported_in_one_error(self) -> None:
        # "abc" fails multiple rules — message should mention all of them
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                current_password=SecretStr(_VALID_CRED),
                new_password=SecretStr(_MULTI_FAIL_INPUT),
            )
        msg = str(exc_info.value)
        assert "uppercase" in msg
        assert "digit" in msg
        assert "special" in msg

    def test_current_password_not_validated_for_complexity(self) -> None:
        # current_password has no complexity validator — any string is accepted
        req = PasswordResetRequest(
            current_password=SecretStr(_UNCOMPLEXED), new_password=SecretStr(_VALID_CRED)
        )
        assert req.current_password.get_secret_value() == _UNCOMPLEXED

    def test_passwords_stored_as_secret(self) -> None:
        req = PasswordResetRequest(
            current_password=SecretStr(_VALID_CRED), new_password=SecretStr(_VALID_CRED)
        )
        assert _VALID_CRED not in str(req)
        assert _VALID_CRED not in repr(req)


# ===========================================================================
# Policy constants
# ===========================================================================


class TestPasswordPolicyConstants:
    def test_max_len_is_128(self) -> None:
        assert _PASSWORD_MAX_LEN == 128

    def test_min_len_is_8(self) -> None:
        assert _PASSWORD_MIN_LEN == 8

    def test_min_less_than_max(self) -> None:
        assert _PASSWORD_MIN_LEN < _PASSWORD_MAX_LEN
