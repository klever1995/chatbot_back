from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel  # <-- NUEVO
from app.db.base import get_db
from app.models.usuarios import Usuario
from app.schemas.usuarios import Token
from app.services.auth_google import verify_google_token
from app.api.v1.endpoints.usuarios import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
import logging

router = APIRouter(prefix="/auth", tags=["autenticación"])
logger = logging.getLogger(__name__)

# NUEVO: Modelo para recibir el token en el body
class GoogleAuthRequest(BaseModel):
    credential: str

def get_or_create_user_google(db: Session, google_data: dict) -> Usuario:
    """
    Busca al usuario por email o google_id; si no existe, lo crea.
    """
    # Buscar por google_id o email
    user = db.query(Usuario).filter(
        (Usuario.google_id == google_data["google_id"]) | 
        (Usuario.email == google_data["email"])
    ).first()

    if not user:
        # Crear nuevo usuario
        user = Usuario(
            email=google_data["email"],
            nombre=google_data["nombre"],
            google_id=google_data["google_id"],
            foto_url=google_data.get("foto_url"),
            auth_provider="google",
            empresa_id=1,  # ⚠️ IMPORTANTE: Definir cómo asignar empresa
            rol="empleado",  # Rol por defecto
            activo=True,
            password_hash=None  # No tiene contraseña
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Nuevo usuario creado vía Google: {user.email}")
    else:
        # Actualizar datos que pueden cambiar
        user.nombre = google_data["nombre"]
        user.foto_url = google_data.get("foto_url")
        if not user.google_id:
            user.google_id = google_data["google_id"]
        if user.auth_provider == "local":
            # Si ya existía como local, ahora también tendrá Google
            user.auth_provider = "google"
        db.commit()
        db.refresh(user)
        logger.info(f"Usuario actualizado vía Google: {user.email}")

    return user

@router.post("/google", response_model=Token)
async def login_google(
    request: GoogleAuthRequest,  # <-- CAMBIADO: ahora recibe el body
    db: Session = Depends(get_db)
):
    """
    Endpoint para login/registro con Google
    Recibe el token de credencial de Google y devuelve un JWT
    """
    try:
        # Verificar token de Google
        google_data = verify_google_token(request.credential)  # <-- CAMBIADO
        
        # Obtener o crear usuario
        user = get_or_create_user_google(db, google_data)
        
        # Crear token JWT para tu app
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "empresa_id": user.empresa_id,
                "email": user.email,
                "rol": user.rol
            },
            expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except ValueError as e:
        logger.error(f"Error en login Google: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error inesperado en login Google: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )