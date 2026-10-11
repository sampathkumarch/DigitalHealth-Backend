import hashlib
import hmac
import secrets


def generate_otp(length: int) -> str:
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_code(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
