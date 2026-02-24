from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class EmpresaBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    telefono_whatsapp: str = Field(..., max_length=20)
    prompt_personalizado: Optional[str] = None
    telefono_dueño: Optional[str] = Field(None, max_length=20)
    activa: Optional[bool] = True

class EmpresaCreate(EmpresaBase):
    pass

class Empresa(EmpresaBase):
    id: int
    token_api: str
    fecha_registro: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True