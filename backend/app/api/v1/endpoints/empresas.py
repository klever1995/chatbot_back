from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import secrets

from app.db.base import get_db
from app.models.empresa import Empresa as EmpresaModel
from app.schemas.empresa import Empresa, EmpresaCreate, EmpresaUpdate

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
    
    # Crear nueva empresa con todos los campos
    nueva_empresa = EmpresaModel(
        nombre=empresa.nombre,
        telefono_whatsapp=empresa.telefono_whatsapp,
        prompt_personalizado=empresa.prompt_personalizado,
        telefono_dueño=empresa.telefono_dueño,
        activa=empresa.activa,
        token_api=token_api,
        whatsapp_token=empresa.whatsapp_token,
        phone_number_id=empresa.phone_number_id,
        verify_token=empresa.verify_token,
        openai_api_key=empresa.openai_api_key,
        openai_embedding_model=empresa.openai_embedding_model,
        openai_chat_model=empresa.openai_chat_model,
        openai_api_base=empresa.openai_api_base,
        groq_api_key=empresa.groq_api_key,
        cloudinary_cloud_name=empresa.cloudinary_cloud_name,
        cloudinary_api_key=empresa.cloudinary_api_key,
        cloudinary_api_secret=empresa.cloudinary_api_secret
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

@router.put("/{empresa_id}", response_model=Empresa)
def actualizar_empresa(
    empresa_id: int, 
    empresa_data: EmpresaUpdate, 
    db: Session = Depends(get_db)
):
    """
    Actualiza los datos de una empresa existente
    """
    # Buscar la empresa
    empresa = db.query(EmpresaModel).filter(EmpresaModel.id == empresa_id).first()
    
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )
    
    # Verificar si el nuevo teléfono ya está usado por otra empresa
    if empresa_data.telefono_whatsapp and empresa.telefono_whatsapp != empresa_data.telefono_whatsapp:
        telefono_existe = db.query(EmpresaModel).filter(
            EmpresaModel.telefono_whatsapp == empresa_data.telefono_whatsapp,
            EmpresaModel.id != empresa_id
        ).first()
        
        if telefono_existe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otra empresa con este número de WhatsApp"
            )
    
    # Actualizar solo los campos que vienen en la petición
    update_data = empresa_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(empresa, field, value)
    
    db.commit()
    db.refresh(empresa)
    
    return empresa