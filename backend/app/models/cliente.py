from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    telefono = Column(String(20), nullable=False, index=True)
    nombre = Column(String(100), nullable=True)
    resumen = Column(Text, nullable=True)  # Resumen generado por LLM de las conversaciones
    datos_estructurados = Column(JSON, nullable=True)  # Ej: {"producto_interes": "tazas", "tipo_cliente": "corporativo"}
    sentimiento_ultimo = Column(String(20), default="neutral")
    ultima_interaccion = Column(DateTime(timezone=True), onupdate=func.now())
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())

    # Relación con empresa
    empresa = relationship("Empresa", backref="clientes")

    def __repr__(self):
        return f"<Cliente {self.telefono} de empresa {self.empresa_id}>"