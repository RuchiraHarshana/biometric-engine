from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

# Use PBKDF2-SHA256 as the default hashing scheme for environments
# where the bcrypt backend may be unavailable; keep bcrypt in the
# list so existing bcrypt hashes can still be verified.
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: int = JWT_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Convert sub back to int for DB lookups
        if "sub" in payload:
            try:
                payload["sub"] = int(payload["sub"])
            except Exception:
                pass
        return payload
    except (JWTError, ValueError):
        return None


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="BioSecureGate")


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
