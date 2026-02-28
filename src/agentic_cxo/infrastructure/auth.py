"""
Authentication — signup, login, JWT tokens, session management.

Every API call requires a valid JWT token. The founder signs up,
gets a token, and all their data is scoped to their user ID.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from agentic_cxo.config import settings as app_settings

logger = logging.getLogger(__name__)

SECRET_KEY = app_settings.auth.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    pwd_context.hash("test")
except Exception:
    pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

DATA_DIR = Path(".cxo_data")


class User:
    def __init__(
        self,
        user_id: str,
        email: str,
        hashed_password: str,
        name: str = "",
        created_at: str = "",
        role: str = "founder",
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.hashed_password = hashed_password
        self.name = name
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.role = role

    def to_dict(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "hashed_password": self.hashed_password,
            "name": self.name,
            "created_at": self.created_at,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> User:
        return cls(**d)

    def public_dict(self) -> dict[str, str]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
        }


class UserStore:
    """Persistent user storage."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._load()

    def _path(self) -> Path:
        DATA_DIR.mkdir(exist_ok=True)
        return DATA_DIR / "users.json"

    def _load(self) -> None:
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for d in data:
                    u = User.from_dict(d)
                    self._users[u.email] = u
            except Exception:
                logger.warning("Could not load users")

    def save(self) -> None:
        self._path().write_text(
            json.dumps([u.to_dict() for u in self._users.values()], indent=2)
        )

    def create(self, email: str, password: str, name: str = "") -> User:
        if email in self._users:
            raise ValueError("User already exists")
        user = User(
            user_id=uuid.uuid4().hex[:16],
            email=email,
            hashed_password=pwd_context.hash(password),
            name=name,
        )
        self._users[email] = user
        self.save()
        return user

    def authenticate(self, email: str, password: str) -> User | None:
        user = self._users.get(email)
        if user and pwd_context.verify(password, user.hashed_password):
            return user
        return None

    def get_by_email(self, email: str) -> User | None:
        return self._users.get(email)

    def get_by_id(self, user_id: str) -> User | None:
        for u in self._users.values():
            if u.user_id == user_id:
                return u
        return None

    @property
    def count(self) -> int:
        return len(self._users)


class AuthManager:
    """Handles token creation and verification."""

    def __init__(self) -> None:
        self.store = UserStore()

    def signup(
        self, email: str, password: str, name: str = ""
    ) -> dict[str, Any]:
        try:
            user = self.store.create(email, password, name)
        except ValueError:
            return {"error": "Email already registered"}
        token = self._create_token(user)
        return {"user": user.public_dict(), "token": token}

    def login(self, email: str, password: str) -> dict[str, Any]:
        user = self.store.authenticate(email, password)
        if not user:
            return {"error": "Invalid email or password"}
        token = self._create_token(user)
        return {"user": user.public_dict(), "token": token}

    def verify_token(self, token: str) -> User | None:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                return None
            return self.store.get_by_id(user_id)
        except JWTError:
            return None

    @staticmethod
    def _create_token(user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=ACCESS_TOKEN_EXPIRE_HOURS
        )
        return jwt.encode(
            {"sub": user.user_id, "email": user.email, "exp": expire},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
