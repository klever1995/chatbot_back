from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# Schema base con campos comunes
class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: str
    rol: Optional[str] = "empleado"
    activo: Optional[bool] = True

# Schema para crear usuario (registro)
class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=6, description="Contraseña mínima 6 caracteres")
    empresa_id: int  # Se asignará al crear, normalmente del dueño

# Schema para login
class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str

# Schema para respuesta (lo que devuelve la API)
class UsuarioResponse(UsuarioBase):
    id: int
    empresa_id: int
    ultimo_acceso: Optional[datetime] = None
    fecha_registro: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema para token JWT
class Token(BaseModel):
    access_token: str
    token_type: str

# Schema para datos del token
class TokenData(BaseModel):
    usuario_id: Optional[int] = None
    empresa_id: Optional[int] = None
    email: Optional[str] = None
    rol: Optional[str] = None

# Schema para actualizar usuario
class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    rol: Optional[str] = None
    activo: Optional[bool] = None