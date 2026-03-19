from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.schemas.auth import GoogleAuthRequest, TokenResponse
from app.services.auth_service import verify_google_token, get_or_create_user
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post("/google", response_model=TokenResponse)
def login_with_google(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Verifica el id_token de Google, crea o recupera al usuario
    y retorna un JWT propio de la aplicación.
    """
    try:
        google_data = verify_google_token(payload.credential)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de Google inválido: {str(e)}"
        )

    user = get_or_create_user(db, google_data)

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }
