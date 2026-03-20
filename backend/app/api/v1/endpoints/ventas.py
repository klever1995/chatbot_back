from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime

from app.db.base import get_db
from app.models.ventas import Venta
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.schemas.ventas import VentaCreate, VentaUpdate, VentaResponse, VentaFilter, EstadoVenta

router = APIRouter(prefix="/ventas", tags=["ventas"])

@router.post("/", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
def crear_venta(
    venta: VentaCreate,
    db: Session = Depends(get_db)
):
    """
    Crear una nueva venta
    """
    # Verificar que la empresa existe
    empresa = db.query(Empresa).filter(Empresa.id == venta.empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    # Verificar que el cliente existe
    cliente = db.query(Cliente).filter(Cliente.id == venta.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )
    
    # Calcular monto_total si no se proporcionó
    monto_total = venta.monto_total
    if monto_total is None:
        monto_total = venta.cantidad * venta.precio_unitario
    
    # Crear la venta
    nueva_venta = Venta(
        empresa_id=venta.empresa_id,
        cliente_id=venta.cliente_id,
        campania_id=venta.campania_id,
        producto_nombre=venta.producto_nombre,
        cantidad=venta.cantidad,
        precio_unitario=venta.precio_unitario,
        monto_total=monto_total,
        estado=venta.estado,
        comprobante_url=venta.comprobante_url,
        notas=venta.notas
    )
    
    db.add(nueva_venta)
    db.commit()
    db.refresh(nueva_venta)
    
    return nueva_venta

@router.get("/", response_model=List[dict])
def listar_ventas(
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa"),
    cliente_id: Optional[int] = Query(None, description="Filtrar por cliente"),
    campania_id: Optional[str] = Query(None, description="Filtrar por campaña"),
    estado: Optional[EstadoVenta] = Query(None, description="Filtrar por estado"),
    fecha_desde: Optional[datetime] = Query(None, description="Ventas desde esta fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Ventas hasta esta fecha"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Listar ventas con filtros opcionales e información del cliente
    """
    # Usar joinedload para cargar los datos del cliente en la misma consulta
    query = db.query(Venta).options(joinedload(Venta.cliente))
    
    # Aplicar filtros
    if empresa_id:
        query = query.filter(Venta.empresa_id == empresa_id)
    if cliente_id:
        query = query.filter(Venta.cliente_id == cliente_id)
    if campania_id:
        query = query.filter(Venta.campania_id == campania_id)
    if estado:
        query = query.filter(Venta.estado == estado)
    if fecha_desde:
        query = query.filter(Venta.fecha_venta >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Venta.fecha_venta <= fecha_hasta)
    
    # Ordenar por fecha descendente (más recientes primero)
    query = query.order_by(Venta.fecha_venta.desc())
    
    # Paginar
    ventas = query.offset(skip).limit(limit).all()
    
    # Construir respuesta incluyendo datos del cliente
    resultado = []
    for venta in ventas:
        venta_dict = {
            "id": venta.id,
            "empresa_id": venta.empresa_id,
            "cliente_id": venta.cliente_id,
            "cliente_nombre": venta.cliente.nombre if venta.cliente else None,
            "cliente_telefono": venta.cliente.telefono if venta.cliente else None,
            "campania_id": venta.campania_id,
            "producto_nombre": venta.producto_nombre,
            "cantidad": venta.cantidad,
            "precio_unitario": venta.precio_unitario,
            "monto_total": venta.monto_total,
            "estado": venta.estado,
            "comprobante_url": venta.comprobante_url,
            "notas": venta.notas,
            "fecha_venta": venta.fecha_venta.isoformat() if venta.fecha_venta else None,
            "fecha_actualizacion": venta.fecha_actualizacion.isoformat() if venta.fecha_actualizacion else None
        }
        resultado.append(venta_dict)
    
    return resultado

@router.get("/{venta_id}", response_model=VentaResponse)
def obtener_venta(
    venta_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener una venta por su ID
    """
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada"
        )
    return venta

@router.put("/{venta_id}", response_model=VentaResponse)
def actualizar_venta(
    venta_id: int,
    venta_update: VentaUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar una venta existente
    """
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada"
        )
    
    # Actualizar solo los campos proporcionados
    update_data = venta_update.dict(exclude_unset=True)
    
    # Si se actualizó cantidad o precio_unitario, recalcular monto_total
    if "cantidad" in update_data or "precio_unitario" in update_data:
        nueva_cantidad = update_data.get("cantidad", venta.cantidad)
        nuevo_precio = update_data.get("precio_unitario", venta.precio_unitario)
        update_data["monto_total"] = nueva_cantidad * nuevo_precio
    
    for field, value in update_data.items():
        setattr(venta, field, value)
    
    # Actualizar fecha de actualización automáticamente
    venta.fecha_actualizacion = datetime.now()
    
    db.commit()
    db.refresh(venta)
    
    return venta

@router.delete("/{venta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_venta(
    venta_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar una venta (solo para administración)
    """
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada"
        )
    
    db.delete(venta)
    db.commit()
    
    return None

@router.get("/estadisticas/resumen")
def obtener_estadisticas(
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa"),
    campania_id: Optional[str] = Query(None, description="Filtrar por campaña"),
    fecha_desde: Optional[datetime] = Query(None, description="Desde fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Hasta fecha"),
    db: Session = Depends(get_db)
):
    """
    Obtener estadísticas resumidas de ventas
    """
    query = db.query(Venta).filter(Venta.estado == EstadoVenta.CONFIRMADA)
    
    if empresa_id:
        query = query.filter(Venta.empresa_id == empresa_id)
    if campania_id:
        query = query.filter(Venta.campania_id == campania_id)
    if fecha_desde:
        query = query.filter(Venta.fecha_venta >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Venta.fecha_venta <= fecha_hasta)
    
    ventas = query.all()
    
    total_ventas = len(ventas)
    total_ingresos = sum(v.monto_total for v in ventas)
    promedio_venta = total_ingresos / total_ventas if total_ventas > 0 else 0
    
    return {
        "total_ventas": total_ventas,
        "total_ingresos": round(total_ingresos, 2),
        "promedio_venta": round(promedio_venta, 2),
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta
    }