from os import getenv


class EnvVarRequired(Exception):
    """
    Raised when an environment variable which is required is not set.
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"{key} is a required environment variable.")


def get_required_env(key: str) -> str:
    """
    Pulls `key` from .env, if it doesn't exist, then an error is thrown.
    """
    # Try to getenv(key)...
    tmp = getenv(key, None)

    # If key is not found, then raise an error
    if tmp is None:
        raise EnvVarRequired(key)

    # If key IS found, then return the key and life is good
    return tmp


__all__ = ["EnvVarRequired", "get_required_env"]
