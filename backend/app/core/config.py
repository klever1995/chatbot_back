import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    # Puedes agregar aquí otras variables de entorno que uses
    SECRET_KEY: str = os.getenv("SECRET_KEY", "tu_secreto_super_seguro_cambia_esto")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()