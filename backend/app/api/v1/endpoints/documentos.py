from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
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
    
    try:
        # Leer contenido del archivo
        contenido = await archivo.read()
        
        # Procesar documento con RAG
        rag_service = RAGService(db, empresa_id)
        documento = rag_service.guardar_documento(archivo.filename, contenido)
        
        return {
            "mensaje": "Documento procesado correctamente",
            "documento_id": documento.id,
            "nombre": documento.nombre,
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
            "total_chunks": len(doc.chunks) if doc.chunks else 0
        }
        for doc in documentos
    ]

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