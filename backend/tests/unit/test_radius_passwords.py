"""Unit tests for RADIUS password hashing (issue #96: NT-Password).

The backend image's OpenSSL 3 build does not provide MD4 through hashlib
(``ValueError: unsupported hash type md4``), so NT-Password uses a pure
Python MD4 checked here against the RFC 1320 test suite.
"""

import hashlib

import pytest

from app.core.radius_passwords import hash_password_value, md4_hex, nt_hash


@pytest.mark.parametrize(
    "message, digest",
    [
        (b"", "31d6cfe0d16ae931b73c59d7e0c089c0"),
        (b"a", "bde52cb31de33e46245e05fbdbd6fb24"),
        (b"abc", "a448017aaf21d8525fc10ae87aa6729d"),
        (b"message digest", "d9130a8164549fe818874806e1c7014b"),
        (b"abcdefghijklmnopqrstuvwxyz", "d79e1c308aa5bbcdeea8ed63df412da9"),
        (
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
            "043f8582f241db351ce627e153e7f0e4",
        ),
        (b"1234567890" * 8, "e33b4ddc9c38f2199c3e7b164fcc0536"),
    ],
)
def test_md4_matches_rfc1320_test_suite(message, digest):
    assert md4_hex(message) == digest


def test_nt_hash_is_md4_of_utf16le_password():
    # Well-known NT hash of "password"
    assert nt_hash("password") == "8846f7eaee8fb117ad06bdd830b7586c"
    assert nt_hash("ñandú") == md4_hex("ñandú".encode("utf-16-le"))


def test_hash_password_value_per_attribute():
    assert hash_password_value("NT-Password", "password") == "8846f7eaee8fb117ad06bdd830b7586c"
    assert hash_password_value("nt-password", "password") == "8846f7eaee8fb117ad06bdd830b7586c"
    assert hash_password_value("MD5-Password", "pw") == hashlib.md5(b"pw").hexdigest()
    assert hash_password_value("md5-password", "pw") == hashlib.md5(b"pw").hexdigest()
    assert hash_password_value("Cleartext-Password", "pw") == "pw"
    assert hash_password_value("Expiration", "01 Jan 2030 00:00") == "01 Jan 2030 00:00"
