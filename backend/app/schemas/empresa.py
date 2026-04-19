from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class EmpresaBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    telefono_whatsapp: str = Field(..., max_length=20)
    prompt_personalizado: Optional[str] = None
    telefono_dueño: Optional[str] = Field(None, max_length=20)
    activa: Optional[bool] = True
    
    # 🔥 NUEVOS CAMPOS
    whatsapp_token: str = Field(..., max_length=500)
    phone_number_id: str = Field(..., max_length=100)
    verify_token: str = Field(..., max_length=100)
    openai_api_key: str = Field(..., max_length=500)
    openai_embedding_model: Optional[str] = Field("text-embedding-ada-002", max_length=100)
    openai_chat_model: Optional[str] = Field("gpt-4o", max_length=100)
    openai_api_base: Optional[str] = Field(None, max_length=500)
    groq_api_key: str = Field(..., max_length=500)
    cloudinary_cloud_name: str = Field(..., max_length=100)
    cloudinary_api_key: str = Field(..., max_length=100)
    cloudinary_api_secret: str = Field(..., max_length=500)

class EmpresaCreate(EmpresaBase):
    pass

class Empresa(EmpresaBase):
    id: int
    token_api: str
    fecha_registro: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    telefono_whatsapp: Optional[str] = Field(None, max_length=20)
    prompt_personalizado: Optional[str] = None
    telefono_dueño: Optional[str] = Field(None, max_length=20)
    activa: Optional[bool] = None
    whatsapp_token: Optional[str] = Field(None, max_length=500)
    phone_number_id: Optional[str] = Field(None, max_length=100)
    verify_token: Optional[str] = Field(None, max_length=100)
    openai_api_key: Optional[str] = Field(None, max_length=500)
    openai_embedding_model: Optional[str] = Field(None, max_length=100)
    openai_chat_model: Optional[str] = Field(None, max_length=100)
    openai_api_base: Optional[str] = Field(None, max_length=500)
    groq_api_key: Optional[str] = Field(None, max_length=500)
    cloudinary_cloud_name: Optional[str] = Field(None, max_length=100)
    cloudinary_api_key: Optional[str] = Field(None, max_length=100)
    cloudinary_api_secret: Optional[str] = Field(None, max_length=500)
