"""Encrypted blob helpers for platform connection secrets (tokens/cookies).

Never stores platform passwords — only OAuth tokens or session cookies the
user deposits after an official login / Connect session flow.

Uses Fernet-compatible AES when `cryptography` is installed; otherwise a
stdlib XOR+HMAC scaffold suitable for local/dev vaults.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.config import settings


def _key_bytes() -> bytes:
    raw = (settings.connection_vault_key or "rivalradar-dev-vault-key").encode("utf-8")
    return hashlib.sha256(raw).digest()


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    key = base64.urlsafe_b64encode(_key_bytes())
    return Fernet(key)


def encrypt_json(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    f = _fernet()
    if f is not None:
        return f.encrypt(data).decode("utf-8")
    key = _key_bytes()
    nonce = hashlib.sha256(data[:16] + key).digest()[:16]
    stream = hashlib.sha256(key + nonce).digest()
    out = bytearray()
    for i, b in enumerate(data):
        out.append(b ^ stream[i % len(stream)])
    mac = hmac.new(key, nonce + bytes(out), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + bytes(out)).decode("utf-8")


def decrypt_json(blob: str) -> dict[str, Any]:
    f = _fernet()
    if f is not None and blob.startswith("gAAAA"):
        raw = f.decrypt(blob.encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid vault payload")
        return data
    packed = base64.urlsafe_b64decode(blob.encode("utf-8"))
    nonce, mac, ct = packed[:16], packed[16:48], packed[48:]
    key = _key_bytes()
    expect = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expect):
        raise ValueError("vault MAC mismatch")
    stream = hashlib.sha256(key + nonce).digest()
    plain = bytes(b ^ stream[i % len(stream)] for i, b in enumerate(ct))
    data = json.loads(plain.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid vault payload")
    return data
