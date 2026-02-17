from pydantic import BaseModel


class LoginResponse(BaseModel):
    """
    A response that holds a JWT token for authentication
    in CodeCrunchr
    """

    token: str


__all__ = ["LoginResponse"]
