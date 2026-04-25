from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime

from app.db.base import get_db
from app.models.pedido import Pedido, EstadoPedido
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.schemas.pedido import PedidoCreate, PedidoUpdate, PedidoResponse, PedidoFilter

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
def crear_pedido(
    pedido: PedidoCreate,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo pedido (normalmente lo crea el bot automáticamente)
    """
    # Verificar que la empresa existe
    empresa = db.query(Empresa).filter(Empresa.id == pedido.empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    # Verificar que el cliente existe
    cliente = db.query(Cliente).filter(Cliente.id == pedido.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado"
        )
    
    # Crear el pedido
    nuevo_pedido = Pedido(
        empresa_id=pedido.empresa_id,
        cliente_id=pedido.cliente_id,
        campania_id=pedido.campania_id,
        texto_pedido=pedido.texto_pedido,
        monto_total=pedido.monto_total,
        comprobante_url=pedido.comprobante_url,
        estado=pedido.estado,
        notas=pedido.notas
    )
    
    db.add(nuevo_pedido)
    db.commit()
    db.refresh(nuevo_pedido)
    
    return nuevo_pedido

@router.get("/", response_model=List[dict])
def listar_pedidos(
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa"),
    cliente_id: Optional[int] = Query(None, description="Filtrar por cliente"),
    campania_id: Optional[str] = Query(None, description="Filtrar por campaña"),
    estado: Optional[EstadoPedido] = Query(None, description="Filtrar por estado"),
    fecha_desde: Optional[datetime] = Query(None, description="Pedidos desde esta fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Pedidos hasta esta fecha"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Listar pedidos con filtros opcionales e información del cliente
    """
    # Usar joinedload para cargar los datos del cliente en la misma consulta
    query = db.query(Pedido).options(joinedload(Pedido.cliente))
    
    # Aplicar filtros
    if empresa_id:
        query = query.filter(Pedido.empresa_id == empresa_id)
    if cliente_id:
        query = query.filter(Pedido.cliente_id == cliente_id)
    if campania_id:
        query = query.filter(Pedido.campania_id == campania_id)
    if estado:
        query = query.filter(Pedido.estado == estado)
    if fecha_desde:
        query = query.filter(Pedido.fecha_creacion >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Pedido.fecha_creacion <= fecha_hasta)
    
    # Ordenar por fecha descendente (más recientes primero)
    query = query.order_by(Pedido.fecha_creacion.desc())
    
    # Paginar
    pedidos = query.offset(skip).limit(limit).all()
    
    # Construir respuesta incluyendo datos del cliente
    resultado = []
    for pedido in pedidos:
        pedido_dict = {
            "id": pedido.id,
            "empresa_id": pedido.empresa_id,
            "cliente_id": pedido.cliente_id,
            "cliente_nombre": pedido.cliente.nombre if pedido.cliente else None,
            "cliente_telefono": pedido.cliente.telefono if pedido.cliente else None,
            "campania_id": pedido.campania_id,
            "texto_pedido": pedido.texto_pedido,
            "monto_total": pedido.monto_total,
            "comprobante_url": pedido.comprobante_url,
            "estado": pedido.estado,
            "notas": pedido.notas,
            "fecha_creacion": pedido.fecha_creacion.isoformat() if pedido.fecha_creacion else None,
            "fecha_confirmacion": pedido.fecha_confirmacion.isoformat() if pedido.fecha_confirmacion else None
        }
        resultado.append(pedido_dict)
    
    return resultado

@router.get("/{pedido_id}", response_model=PedidoResponse)
def obtener_pedido(
    pedido_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener un pedido por su ID
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )
    return pedido

@router.put("/{pedido_id}", response_model=PedidoResponse)
def actualizar_pedido(
    pedido_id: int,
    pedido_update: PedidoUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar un pedido existente (cambiar estado, notas, etc.)
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )
    
    # Actualizar solo los campos proporcionados
    update_data = pedido_update.dict(exclude_unset=True)
    
    # Si se está confirmando el pedido, actualizar fecha_confirmacion
    if "estado" in update_data and update_data["estado"] == EstadoPedido.CONFIRMADO and pedido.estado != EstadoPedido.CONFIRMADO:
        update_data["fecha_confirmacion"] = datetime.now()
    
    for field, value in update_data.items():
        setattr(pedido, field, value)
    
    db.commit()
    db.refresh(pedido)
    
    return pedido

@router.delete("/{pedido_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar un pedido (solo para administración)
    """
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )
    
    db.delete(pedido)
    db.commit()
    
    return None

@router.get("/estadisticas/resumen")
def obtener_estadisticas_pedidos(
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa"),
    campania_id: Optional[str] = Query(None, description="Filtrar por campaña"),
    fecha_desde: Optional[datetime] = Query(None, description="Desde fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Hasta fecha"),
    db: Session = Depends(get_db)
):
    """
    Obtener estadísticas resumidas de pedidos confirmados
    """
    query = db.query(Pedido).filter(Pedido.estado == EstadoPedido.CONFIRMADO)
    
    if empresa_id:
        query = query.filter(Pedido.empresa_id == empresa_id)
    if campania_id:
        query = query.filter(Pedido.campania_id == campania_id)
    if fecha_desde:
        query = query.filter(Pedido.fecha_creacion >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Pedido.fecha_creacion <= fecha_hasta)
    
    pedidos = query.all()
    
    total_pedidos = len(pedidos)
    total_ingresos = sum(p.monto_total for p in pedidos)
    promedio_pedido = total_ingresos / total_pedidos if total_pedidos > 0 else 0
    
    return {
        "total_pedidos": total_pedidos,
        "total_ingresos": round(total_ingresos, 2),
        "promedio_pedido": round(promedio_pedido, 2),
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta
    }