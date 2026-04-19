import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from typing import Optional, Dict

def configurar_cloudinary(cloud_name: str, api_key: str, api_secret: str):
    """
    Configura Cloudinary con las credenciales de una empresa específica.
    """
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret
    )

def subir_imagen_desde_url(
    url_imagen: str,
    cloud_name: str,
    api_key: str,
    api_secret: str,
    public_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Sube una imagen a Cloudinary proporcionando una URL pública.
    Nota: No funciona con URLs protegidas de WhatsApp (requieren token).
    """
    try:
        configurar_cloudinary(cloud_name, api_key, api_secret)
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
        print(f"❌ Error subiendo imagen a Cloudinary desde URL: {e}")
        return None

def subir_imagen_desde_bytes(
    imagen_bytes: bytes,
    cloud_name: str,
    api_key: str,
    api_secret: str,
    public_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Sube el contenido binario (bytes) de una imagen a Cloudinary.
    Esta es la función que usaremos para las imágenes de WhatsApp.
    """
    try:
        configurar_cloudinary(cloud_name, api_key, api_secret)
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
        print(f"❌ Error subiendo imagen a Cloudinary desde bytes: {e}")
        return None

def obtener_url_imagen(
    public_id: str,
    cloud_name: str,
    api_key: str,
    api_secret: str,
    **options
) -> str:
    """
    Genera una URL optimizada para una imagen ya subida.
    """
    configurar_cloudinary(cloud_name, api_key, api_secret)
    url, _ = cloudinary_url(public_id, **options)
    return url