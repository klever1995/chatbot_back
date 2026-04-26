from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

# Enum para el estado del pedido (coincide con el de la BD)
class EstadoPedido(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    RECHAZADO = "rechazado"

# Schema base con campos comunes
class PedidoBase(BaseModel):
    empresa_id: int
    cliente_id: int
    campania_id: str = Field(..., description="ID de la campaña (ej: restaurante, cafeteria)")
    texto_pedido: str = Field(..., description="Texto completo del pedido escrito por el cliente (ej: 2 pizzas, 3 gaseosas)")
    monto_total: float = Field(..., gt=0, description="Monto total calculado dinámicamente por el bot")
    comprobante_url: Optional[str] = Field(None, description="URL del comprobante en Cloudinary")
    estado: EstadoPedido = Field(default=EstadoPedido.PENDIENTE, description="Estado del pedido")
    notas: Optional[str] = Field(None, description="Notas u observaciones")

# Schema para crear un pedido
class PedidoCreate(PedidoBase):
    pass

# Schema para actualizar un pedido (todos los campos opcionales)
class PedidoUpdate(BaseModel):
    texto_pedido: Optional[str] = None
    monto_total: Optional[float] = Field(None, gt=0)
    comprobante_url: Optional[str] = None
    estado: Optional[EstadoPedido] = None
    notas: Optional[str] = None

# Schema para respuesta (incluye id y fechas)
class PedidoResponse(PedidoBase):
    id: int
    fecha_creacion: datetime
    fecha_confirmacion: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema para filtros de listado
class PedidoFilter(BaseModel):
    empresa_id: Optional[int] = None
    cliente_id: Optional[int] = None
    campania_id: Optional[str] = None
    estado: Optional[EstadoPedido] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None