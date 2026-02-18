from cryptography.fernet import Fernet

from .env import get_required_env

FERNET = Fernet(get_required_env("ENCRYPT_SECRET"))


def encrypt(s: str) -> str:
    """
    Returns a string `s` encoded using Fernet encryption
    and using the ENCRYPT_SECRET from .env
    """
    return FERNET.encrypt(s.encode("utf-8")).decode("utf-8")


def decrypt(s: str) -> str:
    """
    Returns a string `s` decoded from a previously used call to
    the `encrypt()` method in this module.
    """
    return FERNET.decrypt(s.encode("utf-8")).decode("utf-8")
