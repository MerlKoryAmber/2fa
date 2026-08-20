"""MD4 for ldap3 NTLM on Python 3.12+ / OpenSSL 3 (hashlib без MD4)."""

import hashlib


def ensure_md4() -> None:
    try:
        hashlib.new("MD4")
        return
    except ValueError:
        pass

    from Crypto.Hash import MD4 as _MD4

    class _MD4Hash:
        def __init__(self, data: bytes = b""):
            self._h = _MD4.new()
            if data:
                self._h.update(data)

        def update(self, data: bytes) -> None:
            self._h.update(data)

        def digest(self) -> bytes:
            return self._h.digest()

        def hexdigest(self) -> str:
            return self._h.hexdigest()

        def copy(self):
            c = _MD4Hash()
            c._h = self._h.copy()
            return c

    _orig_new = hashlib.new

    def _patched_new(name, data=b"", **kwargs):
        if str(name).upper() == "MD4":
            return _MD4Hash(data)
        return _orig_new(name, data, **kwargs)

    hashlib.new = _patched_new  # type: ignore[assignment]
