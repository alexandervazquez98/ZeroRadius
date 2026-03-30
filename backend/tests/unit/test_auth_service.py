"""
Unit tests: app.core.security module.

Tests password hashing, verification, JWT creation and expiration.
No database access — pure function tests.
"""

from datetime import timedelta

import pytest
from jose import jwt, ExpiredSignatureError

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
)


class TestPasswordHashing:
    """bcrypt hash/verify round-trips."""

    def test_hash_and_verify_correct_password(self):
        password = "MySecureP@ss1!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails_verification(self):
        password = "CorrectPassword!"
        hashed = get_password_hash(password)
        assert verify_password("WrongPassword!", hashed) is False

    def test_empty_password_hash_differs_from_non_empty(self):
        hash1 = get_password_hash("secret")
        hash2 = get_password_hash("")
        # Both are valid bcrypt hashes but different
        assert hash1 != hash2


class TestCreateAccessToken:
    """JWT creation and claims validation."""

    def test_token_contains_correct_sub(self):
        token = create_access_token(data={"sub": "testuser", "role": "admin"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_token_contains_correct_role(self):
        token = create_access_token(data={"sub": "u", "role": "superadmin"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["role"] == "superadmin"

    def test_token_has_exp_claim(self):
        token = create_access_token(data={"sub": "u"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_custom_expiry_is_respected(self):
        """Token with longer expiry should have a later exp than default."""
        short_token = create_access_token(
            data={"sub": "u"}, expires_delta=timedelta(minutes=1)
        )
        long_token = create_access_token(
            data={"sub": "u"}, expires_delta=timedelta(hours=2)
        )
        short_exp = jwt.decode(short_token, SECRET_KEY, algorithms=[ALGORITHM])["exp"]
        long_exp = jwt.decode(long_token, SECRET_KEY, algorithms=[ALGORITHM])["exp"]
        assert long_exp > short_exp

    def test_expired_token_raises_error(self):
        token = create_access_token(
            data={"sub": "u"}, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(ExpiredSignatureError):
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
