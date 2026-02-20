import os
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from typing import Optional, Dict

# Configuración de Cloudinary para gestión de imágenes y archivos multimedia
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

def subir_imagen_desde_url(url_imagen: str, public_id: Optional[str] = None) -> Optional[Dict]:
   
    try:
        resultado = upload(
            url_imagen,
            public_id=public_id,
            folder="comprobantes_pago",
            overwrite=True,
            resource_type="image"
        )
        return {
            "public_id": resultado["public_id"],
            "url": resultado["secure_url"],
            "formato": resultado["format"],
            "tamano": resultado["bytes"]
        }
    except Exception as e:
        print(f"❌ Error subiendo imagen a Cloudinary: {e}")
        return None

def subir_imagen_desde_bytes(imagen_bytes: bytes, public_id: Optional[str] = None) -> Optional[Dict]:
 
    try:
        resultado = upload(
            imagen_bytes,
            public_id=public_id,
            folder="comprobantes_pago",
            overwrite=True,
            resource_type="image"
        )
        return {
            "public_id": resultado["public_id"],
            "url": resultado["secure_url"],
            "formato": resultado["format"],
            "tamano": resultado["bytes"]
        }
    except Exception as e:
        print(f"❌ Error subiendo imagen a Cloudinary: {e}")
        return None

def obtener_url_imagen(public_id: str, **options) -> str:
  
    url, _ = cloudinary_url(public_id, **options)
    return url