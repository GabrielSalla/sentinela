import hashlib
import secrets

MIN_LENGTH = 12
MAX_LENGTH = 128
ITERATIONS = 200_000
SALT_BYTES = 16
SPECIALS = "!@#$%^&*()-_=+[]{}|;:,.<>?/~`"

USERNAME_PATTERN = "^[a-zA-Z0-9_.-]{3,64}$"


def hash_password(password: str) -> tuple[str, str]:
    """Hash a password with PBKDF2-SHA256, returning the '(hash_hex, salt_hex)' tuple"""
    salt = secrets.token_bytes(SALT_BYTES)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return password_hash.hex(), salt.hex()


def verify_dummy(password: str) -> None:
    """Run a password verification that always fails, to equalize login timing"""
    dummy_hash, dummy_salt = hash_password("timing-dummy-password")
    verify_password(password, dummy_hash, dummy_salt)


def verify_password(password: str, password_hash: str | None, salt_hex: str | None) -> bool:
    """Check a password against the stored hash and salt"""
    if not password_hash or not salt_hex:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()
    return secrets.compare_digest(candidate, password_hash)


def validate_password_strength(username: str, password: str) -> list[str]:
    """Validate a password against the strength policy, returning a list of error messages"""
    errors = []
    if len(password) < MIN_LENGTH:
        errors.append(f"password must be at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        errors.append(f"password must be at most {MAX_LENGTH} characters")
    if not any(char.isupper() for char in password):
        errors.append("password must contain at least one uppercase letter")
    if not any(char.islower() for char in password):
        errors.append("password must contain at least one lowercase letter")
    if not any(char.isdigit() for char in password):
        errors.append("password must contain at least one digit")
    if not any(char in SPECIALS for char in password):
        errors.append("password must contain at least one special character")
    if len(username) >= 3 and username.lower() in password.lower():
        errors.append("password must not contain the username")
    return errors
