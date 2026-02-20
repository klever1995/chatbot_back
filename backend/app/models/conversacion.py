from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class TipoEmisor(str, enum.Enum):
    CLIENTE = "cliente"
    BOT = "bot"
    ASESOR = "asesor"

class Conversacion(Base):
    __tablename__ = "conversaciones"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    mensaje = Column(Text, nullable=False)
    emisor = Column(Enum(TipoEmisor), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relación con cliente
    cliente = relationship("Cliente", backref="mensajes")

    def __repr__(self):
        return f"<Mensaje {self.emisor} a las {self.timestamp}>"