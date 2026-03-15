"""
Axora Crypto Utils - thin wrappers (actual encryption lives in ConfigManager)
"""


def encrypt_value(value: str, key: bytes) -> str:
    from cryptography.fernet import Fernet
    return Fernet(key).encrypt(value.encode()).decode()


def decrypt_value(value: str, key: bytes) -> str:
    from cryptography.fernet import Fernet
    return Fernet(key).decrypt(value.encode()).decode()
