#!/usr/bin/env python3
"""Общая расшифровка LinOTP TOTP seed (slot 0 / TOKEN_KEY)."""
from __future__ import annotations

import binascii
import base64

from Crypto.Cipher import AES


def pkcs7_unpad(data: bytes) -> bytes:
    cut = data[-1]
    if cut < 1 or cut > 16 or data[-cut:] != bytes([cut]) * cut:
        raise ValueError("invalid PKCS7 padding")
    return data[:-cut]


def decrypt_totp_seed(keyenc_hex: str, keyiv_hex: str, enc_key: bytes) -> bytes:
    """Raw OTP seed bytes (обычно 20)."""
    if len(enc_key) != 96:
        raise ValueError("encKey must be 96 bytes")
    key = enc_key[0:32]
    cipher = binascii.unhexlify(keyenc_hex)
    iv = binascii.unhexlify(keyiv_hex)
    raw = AES.new(key, AES.MODE_CBC, iv).decrypt(cipher)
    hex_ascii = pkcs7_unpad(raw)
    inner = binascii.a2b_hex(hex_ascii)
    return binascii.unhexlify(inner.decode("ascii"))


def seed_to_base32(seed: bytes) -> str:
    return base64.b32encode(seed).decode("ascii")
