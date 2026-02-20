from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import secrets

from app.db.base import get_db
from app.models.empresa import Empresa as EmpresaModel
from app.schemas.empresa import Empresa, EmpresaCreate

router = APIRouter(prefix="/empresas", tags=["empresas"])

@router.post("/", response_model=Empresa, status_code=status.HTTP_201_CREATED)
def crear_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    # Verificar si ya existe una empresa con ese teléfono
    db_empresa = db.query(EmpresaModel).filter(
        EmpresaModel.telefono_whatsapp == empresa.telefono_whatsapp
    ).first()
    
    if db_empresa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una empresa registrada con este número de WhatsApp"
        )
    
    # Generar token único para la empresa
    token_api = secrets.token_urlsafe(32)
    
    # Crear nueva empresa
    nueva_empresa = EmpresaModel(
        **empresa.model_dump(),
        token_api=token_api
    )
    
    db.add(nueva_empresa)
    db.commit()
    db.refresh(nueva_empresa)
    
    return nueva_empresa

@router.get("/", response_model=List[Empresa])
def listar_empresas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    empresas = db.query(EmpresaModel).offset(skip).limit(limit).all()
    return empresas

@router.get("/{empresa_id}", response_model=Empresa)
def obtener_empresa(empresa_id: int, db: Session = Depends(get_db)):
    empresa = db.query(EmpresaModel).filter(EmpresaModel.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    return empresa