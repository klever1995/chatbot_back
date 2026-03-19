from pydantic import BaseModel
from typing import Optional

class GoogleAuthRequest(BaseModel):
    """Recibe el credential (id_token) que envía el frontend."""
    credential: str

class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    foto_url: Optional[str] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
