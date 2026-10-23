from collections import OrderedDict, deque
from dataclasses import dataclass
import hashlib
import hmac
import secrets
import time
from typing import Callable


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Use uma senha com pelo menos 12 caracteres.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        kind, salt, expected = encoded.split("$")
        if kind != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class AccessSession:
    username: str
    csrf: str
    expires_at: float
    role: str = "operador"


class Sessions:
    def __init__(self, ttl: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self.clock = clock
        self.items: OrderedDict[str, AccessSession] = OrderedDict()
        self.attempts: OrderedDict[str, deque[float]] = OrderedDict()

    def issue(self, username: str) -> tuple[str, AccessSession]:
        self.prune()
        token = secrets.token_urlsafe(32)
        session = AccessSession(username, secrets.token_urlsafe(32), self.clock() + self.ttl)
        self.items[token] = session
        while len(self.items) > 128:
            self.items.popitem(last=False)
        return token, session

    def prune(self) -> None:
        for token in list(self.items):
            if self.items[token].expires_at <= self.clock():
                del self.items[token]

    def get(self, token: str | None) -> AccessSession | None:
        session = self.items.get(token or "")
        if session and session.expires_at > self.clock() and session.role == "operador":
            return session
        self.items.pop(token or "", None)
        return None

    def revoke(self, token: str | None) -> None:
        self.items.pop(token or "", None)

    def permit_attempt(self, address: str) -> bool:
        now = self.clock()
        entries = self.attempts.setdefault(address, deque(maxlen=10))
        self.attempts.move_to_end(address)
        while entries and entries[0] <= now - 60:
            entries.popleft()
        allowed = len(entries) < 5
        if allowed:
            entries.append(now)
        while len(self.attempts) > 256:
            self.attempts.popitem(last=False)
        return allowed
