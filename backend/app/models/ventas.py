from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class EstadoVenta(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    RECHAZADA = "rechazada"
    ENTREGADA = "entregada"

class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    campania_id = Column(String(100), nullable=False, index=True)  # ID de la campaña (ej: "reposteria")
    producto_nombre = Column(String(200), nullable=True)  # Nombre del producto comprado
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Float, nullable=False)
    monto_total = Column(Float, nullable=False)  # cantidad * precio_unitario
    estado = Column(Enum(EstadoVenta), default=EstadoVenta.PENDIENTE)
    fecha_venta = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())
    comprobante_url = Column(String(500), nullable=True)  # URL del comprobante en Cloudinary
    notas = Column(Text, nullable=True)  # Observaciones adicionales
    
    # Relaciones
    empresa = relationship("Empresa", backref="ventas")
    cliente = relationship("Cliente", backref="ventas")

    def __repr__(self):
        return f"<Venta {self.id} - Campaña {self.campania_id} - Cliente {self.cliente_id}>"