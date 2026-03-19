from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session
from app.models.usuario import Usuario
from app.core.config import settings

def verify_google_token(credential: str) -> dict:
    """
    Verifica el id_token de Google y retorna los datos del usuario.
    Lanza ValueError si el token es inválido.
    """
    idinfo = id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID
    )
    return {
        "google_id": idinfo["sub"],
        "email": idinfo["email"],
        "nombre": idinfo.get("name", ""),
        "foto_url": idinfo.get("picture", None),
    }

def get_or_create_user(db: Session, google_data: dict) -> Usuario:
    """Busca al usuario por email; si no existe, lo crea."""
    user = db.query(Usuario).filter(Usuario.email == google_data["email"]).first()

    if not user:
        user = Usuario(
            email=google_data["email"],
            nombre=google_data["nombre"],
            foto_url=google_data["foto_url"],
            google_id=google_data["google_id"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Actualizar datos que pueden cambiar (foto, nombre)
        user.foto_url = google_data["foto_url"]
        user.nombre = google_data["nombre"]
        db.commit()
        db.refresh(user)

    return user
