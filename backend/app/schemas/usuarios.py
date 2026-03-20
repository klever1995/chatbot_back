from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# Schema base con campos comunes
class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: str
    rol: Optional[str] = "empleado"
    activo: Optional[bool] = True
    foto_url: Optional[str] = None  # Nuevo campo
    auth_provider: Optional[str] = "local"  # Nuevo campo

# Schema para crear usuario (registro con email/contraseña)
class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=6, description="Contraseña mínima 6 caracteres")
    empresa_id: int

# Schema para crear usuario desde proveedor social
class UsuarioSocialCreate(BaseModel):
    email: EmailStr
    nombre: str
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None
    foto_url: Optional[str] = None
    auth_provider: str  # "google" o "facebook"
    empresa_id: int  # Necesitamos definir cómo se asigna

# Schema para login
class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str

# Schema para respuesta (lo que devuelve la API)
class UsuarioResponse(UsuarioBase):
    id: int
    empresa_id: int
    google_id: Optional[str] = None  # Nuevo campo
    facebook_id: Optional[str] = None  # Nuevo campo
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
    foto_url: Optional[str] = None  # Nuevo campo