from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float  # 🔥 AÑADÍ Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
from pgvector.sqlalchemy import Vector

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    # Identificador de la campaña (ej: "reposteria", "lettering")
    campania_id = Column(String(100), nullable=True, index=True)  
    nombre = Column(String(255), nullable=False)
    hash_contenido = Column(String(64), unique=True)
    fecha_subida = Column(DateTime(timezone=True), server_default=func.now())
    # 🔥 Mensaje de entrega del producto
    mensaje_entrega = Column(Text, nullable=True)
    # 🔥 NUEVO CAMPO: Precio del producto (para registrar ventas)
    precio = Column(Float, nullable=True)  # Ej: 3.00, 2.50, etc.
    
    # Relaciones
    empresa = relationship("Empresa", backref="documentos")
    chunks = relationship("ChunkDocumento", back_populates="documento", cascade="all, delete-orphan")

class ChunkDocumento(Base):
    __tablename__ = "chunks_documento"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False)
    indice = Column(Integer, nullable=False)
    texto = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    
    # Relaciones
    documento = relationship("Documento", back_populates="chunks")