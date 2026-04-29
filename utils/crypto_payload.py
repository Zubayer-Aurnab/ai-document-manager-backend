"""Fernet helpers for short-lived secrets at rest (e.g. initial password on invite row)."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def fernet_from_secret(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_utf8(secret: str, plaintext: str) -> str:
    return fernet_from_secret(secret).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_utf8(secret: str, ciphertext: str) -> str:
    return fernet_from_secret(secret).decrypt(ciphertext.encode("ascii")).decode("utf-8")
