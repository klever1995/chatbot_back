from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

# Enum para el estado de la venta (coincide con el de la BD)
class EstadoVenta(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    RECHAZADA = "rechazada"

# Schema base con campos comunes
class VentaBase(BaseModel):
    empresa_id: int
    cliente_id: int
    campania_id: str = Field(..., description="ID de la campaña (ej: lettering, reposteria)")
    producto_nombre: Optional[str] = Field(None, description="Nombre del producto comprado")
    cantidad: int = Field(1, ge=1, description="Cantidad de productos")
    precio_unitario: float = Field(..., gt=0, description="Precio unitario del producto")
    monto_total: Optional[float] = Field(None, description="Monto total (se calcula automáticamente)")
    estado: EstadoVenta = Field(default=EstadoVenta.PENDIENTE, description="Estado de la venta")
    comprobante_url: Optional[str] = Field(None, description="URL del comprobante en Cloudinary")
    notas: Optional[str] = Field(None, description="Notas u observaciones")

# Schema para crear una venta (el monto_total es opcional porque se puede calcular)
class VentaCreate(VentaBase):
    pass

# Schema para actualizar una venta (todos los campos opcionales)
class VentaUpdate(BaseModel):
    producto_nombre: Optional[str] = None
    cantidad: Optional[int] = Field(None, ge=1)
    precio_unitario: Optional[float] = Field(None, gt=0)
    monto_total: Optional[float] = None
    estado: Optional[EstadoVenta] = None
    comprobante_url: Optional[str] = None
    notas: Optional[str] = None

# Schema para respuesta (incluye id y fechas)
class VentaResponse(VentaBase):
    id: int
    fecha_venta: datetime
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema para filtros de listado
class VentaFilter(BaseModel):
    empresa_id: Optional[int] = None
    cliente_id: Optional[int] = None
    campania_id: Optional[str] = None
    estado: Optional[EstadoVenta] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None