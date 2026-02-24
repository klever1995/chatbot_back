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

    def __repr__(self):
        return f"<Empresa {self.nombre} ({self.telefono_whatsapp})>"