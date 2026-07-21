import hashlib
import os

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """
    Hashes a password with a salt using SHA-256.
    Returns: (password_hash, salt)
    """
    if not salt:
        salt = os.urandom(16).hex()
    salted = (password + salt).encode('utf-8')
    pwd_hash = hashlib.sha256(salted).hexdigest()
    return pwd_hash, salt

def verify_password(password: str, pwd_hash: str, salt: str) -> bool:
    """
    Verifies a plain-text password against a stored hash and salt.
    """
    if not password or not pwd_hash or not salt:
        return False
    computed_hash, _ = hash_password(password, salt)
    return computed_hash == pwd_hash
