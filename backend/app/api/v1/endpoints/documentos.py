from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import tempfile

from app.db.base import get_db
from app.services.rag import RAGService
from app.models.empresa import Empresa
from app.models.documento import Documento

router = APIRouter(prefix="/documentos", tags=["documentos"])

@router.post("/subir/{empresa_id}")
async def subir_documento(
    empresa_id: int,
    archivo: UploadFile = File(...),
    campania_id: Optional[str] = Form(None),
    mensaje_entrega: Optional[str] = Form(None),
    precio: Optional[float] = Form(None),
    tipo_campania: Optional[str] = Form(default="producto_unico"),  # 🔥 NUEVO: producto_unico, pedido_multiple o informativo
    db: Session = Depends(get_db)
):
    # Verificar que la empresa existe
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    # Validar tipo de archivo
    if not (archivo.filename.endswith('.pdf') or archivo.filename.endswith('.odf')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF u ODF"
        )
    
    # Validar tipo_campania (ahora incluye 'informativo')
    if tipo_campania not in ["producto_unico", "pedido_multiple", "informativo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tipo_campania debe ser 'producto_unico', 'pedido_multiple' o 'informativo'"
        )
    
    try:
        # Leer contenido del archivo
        contenido = await archivo.read()
        
        # Procesar documento con RAG (pasando todos los parámetros)
        rag_service = RAGService(db, empresa_id)
        documento = rag_service.guardar_documento(
            archivo.filename, 
            contenido, 
            campania_id,
            mensaje_entrega,
            precio,
            tipo_campania  # 🔥 Pasar tipo_campania
        )
        
        return {
            "mensaje": "Documento procesado correctamente",
            "documento_id": documento.id,
            "nombre": documento.nombre,
            "campania_id": documento.campania_id,
            "mensaje_entrega": documento.mensaje_entrega,
            "precio": documento.precio,
            "tipo_campania": documento.tipo_campania,  # 🔥 Incluir en respuesta
            "chunks": len(documento.chunks) if documento.chunks else 0
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el documento: {str(e)}"
        )

@router.get("/listar/{empresa_id}")
def listar_documentos(
    empresa_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    documentos = db.query(Documento).filter(
        Documento.empresa_id == empresa_id
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": doc.id,
            "nombre": doc.nombre,
            "fecha_subida": doc.fecha_subida,
            "campania_id": doc.campania_id,
            "mensaje_entrega": doc.mensaje_entrega,
            "precio": doc.precio,
            "tipo_campania": doc.tipo_campania,  # 🔥 Mostrar tipo_campania
            "total_chunks": len(doc.chunks) if doc.chunks else 0
        }
        for doc in documentos
    ]

@router.get("/{documento_id}")
def obtener_documento(
    documento_id: int,
    db: Session = Depends(get_db)
):
    """Obtener detalles completos de un documento específico"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    return {
        "id": documento.id,
        "nombre": documento.nombre,
        "campania_id": documento.campania_id,
        "mensaje_entrega": documento.mensaje_entrega,
        "precio": documento.precio,
        "tipo_campania": documento.tipo_campania,  # 🔥 Incluir tipo_campania
        "fecha_subida": documento.fecha_subida,
        "total_chunks": len(documento.chunks) if documento.chunks else 0,
        "chunks": [
            {
                "indice": chunk.indice,
                "texto_preview": chunk.texto[:200] + "..." if len(chunk.texto) > 200 else chunk.texto
            }
            for chunk in documento.chunks[:5]
        ]
    }

@router.put("/{documento_id}/campania")
def actualizar_campania_documento(
    documento_id: int,
    campania_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Actualizar la campaña de un documento existente"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    documento.campania_id = campania_id
    db.commit()
    db.refresh(documento)
    
    return {
        "mensaje": "Campaña actualizada correctamente",
        "documento_id": documento.id,
        "campania_id": documento.campania_id,
        "mensaje_entrega": documento.mensaje_entrega,
        "precio": documento.precio,
        "tipo_campania": documento.tipo_campania  # 🔥 Incluir tipo_campania
    }

@router.put("/{documento_id}/mensaje")
def actualizar_mensaje_entrega(
    documento_id: int,
    mensaje_entrega: str = Form(...),
    db: Session = Depends(get_db)
):
    """Actualizar el mensaje de entrega de un documento existente"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    documento.mensaje_entrega = mensaje_entrega
    db.commit()
    db.refresh(documento)
    
    return {
        "mensaje": "Mensaje de entrega actualizado correctamente",
        "documento_id": documento.id,
        "mensaje_entrega": documento.mensaje_entrega,
        "precio": documento.precio,
        "tipo_campania": documento.tipo_campania  # 🔥 Incluir tipo_campania
    }

@router.put("/{documento_id}/precio")
def actualizar_precio_documento(
    documento_id: int,
    precio: float = Form(...),
    db: Session = Depends(get_db)
):
    """Actualizar el precio de un documento existente"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    documento.precio = precio
    db.commit()
    db.refresh(documento)
    
    return {
        "mensaje": "Precio actualizado correctamente",
        "documento_id": documento.id,
        "precio": documento.precio,
        "campania_id": documento.campania_id,
        "tipo_campania": documento.tipo_campania  # 🔥 Incluir tipo_campania
    }

@router.put("/{documento_id}/tipo-campania")
def actualizar_tipo_campania(
    documento_id: int,
    tipo_campania: str = Form(...),
    db: Session = Depends(get_db)
):
    """Actualizar el tipo de campaña de un documento (producto_unico, pedido_multiple o informativo)"""
    if tipo_campania not in ["producto_unico", "pedido_multiple", "informativo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tipo_campania debe ser 'producto_unico', 'pedido_multiple' o 'informativo'"
        )
    
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    documento.tipo_campania = tipo_campania
    db.commit()
    db.refresh(documento)
    
    return {
        "mensaje": "Tipo de campaña actualizado correctamente",
        "documento_id": documento.id,
        "tipo_campania": documento.tipo_campania
    }

@router.delete("/{documento_id}")
def eliminar_documento(
    documento_id: int,
    db: Session = Depends(get_db)
):
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )
    
    db.delete(documento)
    db.commit()
    
    return {"mensaje": "Documento eliminado correctamente"}