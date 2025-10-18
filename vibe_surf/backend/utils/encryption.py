"""
Encryption utilities for VibeSurf Backend

Uses machine MAC address for key derivation to encrypt sensitive data like API keys.
"""

import hashlib
import pdb
import uuid
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from getmac import get_mac_address

import logging

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


def derive_key(machine_id: str, salt: bytes = None) -> bytes:
    """Derive encryption key from machine ID."""
    if salt is None:
        # Use a fixed salt for consistency across sessions
        salt = b'vibesurf_warmshao_2025'
    
    # Convert machine_id to bytes
    password = machine_id.encode('utf-8')
    
    # Derive key using PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

def get_local_user_id():
    _curr_user_id = "vibesurf_userid"
    try:
        from uuid_extensions import uuid7str
        import os
        WORKSPACE_DIR = os.getenv('VIBESURF_WORKSPACE', './vibesurf_workspace')
        USER_ID_PATH = os.path.join(WORKSPACE_DIR, 'telemetry', 'userid')

        if not os.path.exists(USER_ID_PATH):
            os.makedirs(os.path.dirname(USER_ID_PATH), exist_ok=True)
            with open(USER_ID_PATH, 'w') as f:
                new_user_id = uuid7str()
                f.write(new_user_id)
            _curr_user_id = new_user_id
        else:
            with open(USER_ID_PATH) as f:
                _curr_user_id = f.read()
        return _curr_user_id
    except Exception as e:
        logger.error(e)
        return _curr_user_id


def get_encryption_key(use_local_userid=False) -> bytes:
    """Get the encryption key for this machine."""
    machine_id1 = ''
    if not use_local_userid:
        machine_id1 = get_mac_address()
    if not machine_id1:
        logger.info("Use local user id as encryption key.")
        # fallback to get user id
        machine_id1 = get_local_user_id()
    return derive_key(machine_id1)

def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt API key using machine-specific key.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        str: Base64 encoded encrypted API key
    """
    if not api_key or api_key.strip() == "":
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(api_key.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt API key: {e}")
        raise ValueError("Encryption failed")

def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt API key using machine-specific key.
    
    Args:
        encrypted_api_key: Base64 encoded encrypted API key
        
    Returns:
        str: Decrypted API key
    """
    if not encrypted_api_key or encrypted_api_key.strip() == "":
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_data = base64.urlsafe_b64decode(encrypted_api_key.encode('utf-8'))
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode('utf-8')
    except Exception as e:
        try:
            key = get_encryption_key(use_local_userid=True)
            fernet = Fernet(key)
            encrypted_data = base64.urlsafe_b64decode(encrypted_api_key.encode('utf-8'))
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise ValueError("Decryption failed")

def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.
    
    Args:
        value: String to check
        
    Returns:
        bool: True if value appears encrypted
    """
    if not value:
        return False
    
    try:
        # Try to decode as base64
        base64.urlsafe_b64decode(value.encode('utf-8'))
        # If it's base64 and contains the Fernet token prefix, likely encrypted
        return len(value) > 50 and '=' in value
    except:
        return False

# Test functions
def test_encryption():
    """Test encryption/decryption functionality."""
    test_api_key = "sk-test123456789"
    
    try:
        # Test encryption
        encrypted = encrypt_api_key(test_api_key)
        print(f"Original: {test_api_key}")
        print(f"Encrypted: {encrypted}")
        
        # Test decryption
        decrypted = decrypt_api_key(encrypted)
        print(f"Decrypted: {decrypted}")
        
        # Verify
        assert test_api_key == decrypted, "Encryption/decryption failed"
        print("✅ Encryption test passed")
        
    except Exception as e:
        print(f"❌ Encryption test failed: {e}")

if __name__ == "__main__":
    test_encryption()