"""Hashing of RADIUS password attributes stored in radcheck.

The API always receives the plaintext password and stores it in the format
the chosen attribute expects:

- ``MD5-Password``: hex MD5 of the password (PAP only).
- ``NT-Password``: hex MD4 of the UTF-16LE password (PAP and MS-CHAPv1/v2),
  issue #96. NT-Password is unsalted and password-equivalent for MS-CHAP
  (pass-the-hash): it avoids cleartext storage but is not strong protection.
- anything else: stored as given.

MD4 is implemented here because the backend image's OpenSSL 3 build does not
expose it through hashlib.
"""

import hashlib
import struct

_MASK = 0xFFFFFFFF


def _rotl(x: int, n: int) -> int:
    x &= _MASK
    return ((x << n) | (x >> (32 - n))) & _MASK


def md4_hex(message: bytes) -> str:
    """MD4 digest (RFC 1320) as lowercase hex."""
    length_bits = (len(message) * 8) & 0xFFFFFFFFFFFFFFFF
    message += b"\x80" + b"\x00" * ((55 - len(message)) % 64)
    message += struct.pack("<Q", length_bits)

    a, b, c, d = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for offset in range(0, len(message), 64):
        x = struct.unpack("<16I", message[offset : offset + 64])
        aa, bb, cc, dd = a, b, c, d

        # Round 1: F(x, y, z) = (x & y) | (~x & z)
        for i in range(16):
            k, s = i, (3, 7, 11, 19)[i % 4]
            f = (b & c) | (~b & d)
            a, b, c, d = d, _rotl(a + f + x[k], s), b, c

        # Round 2: G(x, y, z) = (x & y) | (x & z) | (y & z)
        for i in range(16):
            k, s = (i % 4) * 4 + i // 4, (3, 5, 9, 13)[i % 4]
            g = (b & c) | (b & d) | (c & d)
            a, b, c, d = d, _rotl(a + g + x[k] + 0x5A827999, s), b, c

        # Round 3: H(x, y, z) = x ^ y ^ z
        for i in range(16):
            k = (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)[i]
            s = (3, 9, 11, 15)[i % 4]
            h = b ^ c ^ d
            a, b, c, d = d, _rotl(a + h + x[k] + 0x6ED9EBA1, s), b, c

        a = (a + aa) & _MASK
        b = (b + bb) & _MASK
        c = (c + cc) & _MASK
        d = (d + dd) & _MASK

    return struct.pack("<4I", a, b, c, d).hex()


def nt_hash(password: str) -> str:
    """NT hash: MD4 of the UTF-16LE encoded password, lowercase hex."""
    return md4_hex(password.encode("utf-16-le"))


def hash_password_value(attribute: str, plaintext: str) -> str:
    """Value to store in radcheck for ``attribute`` given the plaintext input."""
    folded = attribute.casefold()
    if folded == "md5-password":
        return hashlib.md5(plaintext.encode()).hexdigest()
    if folded == "nt-password":
        return nt_hash(plaintext)
    return plaintext
