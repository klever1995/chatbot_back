from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.core.config import settings

def verify_google_token(credential: str) -> dict:
    """
    Verifica el id_token de Google y retorna los datos del usuario.
    
    Args:
        credential: El token ID de Google recibido desde el frontend
        
    Returns:
        dict: Diccionario con los datos del usuario:
            - id: ID de Google (sub)
            - email: Email del usuario
            - nombre: Nombre completo
            - foto_url: URL de la foto de perfil (opcional)
            
    Raises:
        ValueError: Si el token es inválido, expiró o el client ID no coincide
    """
    try:
        # Especificamos que este es un token de acceso (no un token de ID)
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # El token debe ser de este cliente específico
        if idinfo['aud'] != settings.GOOGLE_CLIENT_ID:
            raise ValueError("Token no emitido para esta aplicación")

        return {
            "google_id": idinfo["sub"],
            "email": idinfo["email"],
            "nombre": idinfo.get("name", ""),
            "foto_url": idinfo.get("picture", None),
        }

    except ValueError as e:
        # Token inválido (expirado, mal formado, etc.)
        raise ValueError(f"Token de Google inválido: {str(e)}")
    except Exception as e:
        # Cualquier otro error
        raise ValueError(f"Error verificando token de Google: {str(e)}")