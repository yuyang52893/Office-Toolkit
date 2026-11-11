import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(value: str) -> str:
    return _password_hasher.hash(value)


def verify_password(value: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, value)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def normalize_recovery_answer(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()
