from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class EstadoPedido(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    RECHAZADO = "rechazado"

class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    campania_id = Column(String(100), nullable=False, index=True)  # ID de la campaña (ej: "restaurante")
    texto_pedido = Column(Text, nullable=False)  # Lo que el cliente escribió (ej: "2 pizzas, 3 gaseosas")
    monto_total = Column(Float, nullable=False)  # Total calculado dinámicamente por el bot
    comprobante_url = Column(String(500), nullable=True)  # URL del comprobante en Cloudinary
    estado = Column(Enum(EstadoPedido, values_callable=lambda obj: [e.value for e in obj]), default=EstadoPedido.PENDIENTE)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_confirmacion = Column(DateTime(timezone=True), nullable=True)  # Cuando el dueño aprueba
    notas = Column(Text, nullable=True)  # Observaciones adicionales
    
    # Relaciones
    empresa = relationship("Empresa", backref="pedidos")
    cliente = relationship("Cliente", backref="pedidos")

    def __repr__(self):
        return f"<Pedido {self.id} - Campaña {self.campania_id} - Total ${self.monto_total}>"