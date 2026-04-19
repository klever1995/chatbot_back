from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    telefono_whatsapp = Column(String(20), unique=True, nullable=False, index=True)
    token_api = Column(String(100), unique=True, nullable=False)
    prompt_personalizado = Column(Text, nullable=True) 
    telefono_dueño = Column(String(20), nullable=True)  
    activa = Column(Boolean, default=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 🔥 NUEVOS CAMPOS PARA CREDENCIALES POR EMPRESA
    # WhatsApp
    whatsapp_token = Column(String(500), nullable=False)  # Token de acceso de Meta
    phone_number_id = Column(String(100), nullable=False)  # ID del número de WhatsApp
    verify_token = Column(String(100), nullable=False)  # Token de verificación del webhook
    
    # OpenAI
    openai_api_key = Column(String(500), nullable=False)  # API key de OpenAI
    openai_embedding_model = Column(String(100), nullable=True, default="text-embedding-ada-002")
    openai_chat_model = Column(String(100), nullable=True, default="gpt-4o")
    openai_api_base = Column(String(500), nullable=True)  # Para endpoints personalizados (opcional)
    
    # Groq (para transcripciones de audio)
    groq_api_key = Column(String(500), nullable=False)
    
    # Cloudinary
    cloudinary_cloud_name = Column(String(100), nullable=False)
    cloudinary_api_key = Column(String(100), nullable=False)
    cloudinary_api_secret = Column(String(500), nullable=False)

    def __repr__(self):
        return f"<Empresa {self.nombre} ({self.telefono_whatsapp})>"