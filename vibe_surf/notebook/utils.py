import secrets
import string
import hashlib
import hmac
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import os
import stat


def generate_token(length: int = 48) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Length of the token to generate (default: 48)

    Returns:
        Secure random token string

    Raises:
        ValidationError: If length is invalid
    """
    if length < 16:
        raise ValueError("Token length must be at least 16 characters")

    if length > 128:
        raise ValueError("Token length must not exceed 128 characters")

    # Use URL-safe characters for token
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))
