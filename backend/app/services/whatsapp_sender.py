import os
import requests
from typing import Optional, List, Dict, Any

# Obtener variables de entorno
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")

# URL base de la API de Meta
BASE_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"

def enviar_mensaje_whatsapp(
    telefono_destino: str,
    mensaje: str,
    token: Optional[str] = None
) -> dict:
    """
    Envía un mensaje de texto a un número de WhatsApp usando la API de Meta
    
    Args:
        telefono_destino: Número de teléfono del destinatario (con código de país)
        mensaje: Texto del mensaje a enviar
        token: Token de acceso (opcional, usa el del .env por defecto)
    
    Returns:
        dict: Respuesta de la API de Meta o información del error
    """
    # Usar token del .env si no se proporciona uno
    token_usado = token or WHATSAPP_TOKEN
    
    if not token_usado:
        return {
            "exito": False,
            "error": "No hay token de acceso configurado"
        }
    
    # Cabeceras de la petición
    headers = {
        "Authorization": f"Bearer {token_usado}",
        "Content-Type": "application/json"
    }
    
    # Cuerpo del mensaje (formato requerido por Meta)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono_destino,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": mensaje
        }
    }
    
    try:
        # Realizar la petición POST a la API de Meta
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=10  # Timeout de 10 segundos
        )
        
        # Verificar si la petición fue exitosa
        if response.status_code == 200 or response.status_code == 201:
            return {
                "exito": True,
                "data": response.json()
            }
        else:
            return {
                "exito": False,
                "error": f"Error {response.status_code}",
                "detalles": response.json()
            }
            
    except requests.exceptions.Timeout:
        return {
            "exito": False,
            "error": "Timeout al conectar con la API de WhatsApp"
        }
    except requests.exceptions.ConnectionError:
        return {
            "exito": False,
            "error": "Error de conexión con la API de WhatsApp"
        }
    except Exception as e:
        return {
            "exito": False,
            "error": f"Error inesperado: {str(e)}"
        }

def enviar_mensaje_con_plantilla(
    telefono_destino: str,
    nombre_plantilla: str,
    componentes: list = [],
    token: Optional[str] = None
) -> dict:
    """
    Envía un mensaje usando una plantilla aprobada (útil para notificaciones)
    
    Args:
        telefono_destino: Número de teléfono del destinatario
        nombre_plantilla: Nombre de la plantilla en Meta
        componentes: Componentes de la plantilla (cabecera, cuerpo, botones)
        token: Token de acceso (opcional)
    
    Returns:
        dict: Respuesta de la API
    """
    token_usado = token or WHATSAPP_TOKEN
    
    if not token_usado:
        return {"exito": False, "error": "No hay token configurado"}
    
    headers = {
        "Authorization": f"Bearer {token_usado}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "template",
        "template": {
            "name": nombre_plantilla,
            "language": {
                "code": "es"  # Español
            },
            "components": componentes
        }
    }
    
    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            return {"exito": True, "data": response.json()}
        else:
            return {"exito": False, "error": f"Error {response.status_code}", "detalles": response.json()}
            
    except Exception as e:
        return {"exito": False, "error": f"Error: {str(e)}"}

# ===== NUEVA FUNCIÓN PARA BOTONES INTERACTIVOS =====
def enviar_mensaje_con_botones(
    telefono_destino: str,
    texto_cabecera: str,
    cliente_id: int,
    token: Optional[str] = None
) -> dict:
    """
    Envía un mensaje con botones interactivos de aprobar/rechazar
    
    Args:
        telefono_destino: Número del destinatario (dueño)
        texto_cabecera: Texto informativo sobre el cliente/comprobante
        cliente_id: ID del cliente para incluir en el callback_data
        token: Token de acceso (opcional)
    
    Returns:
        dict: Respuesta de la API
    """
    token_usado = token or WHATSAPP_TOKEN
    
    if not token_usado:
        return {"exito": False, "error": "No hay token configurado"}
    
    headers = {
        "Authorization": f"Bearer {token_usado}",
        "Content-Type": "application/json"
    }
    
    # Crear el payload con botones interactivos
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono_destino,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": texto_cabecera
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"APROBAR_{cliente_id}",
                            "title": "✅ APROBAR"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"RECHAZAR_{cliente_id}",
                            "title": "❌ RECHAZAR"
                        }
                    }
                ]
            }
        }
    }
    
    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            return {"exito": True, "data": response.json()}
        else:
            return {"exito": False, "error": f"Error {response.status_code}", "detalles": response.json()}
            
    except requests.exceptions.Timeout:
        return {"exito": False, "error": "Timeout al conectar con la API de WhatsApp"}
    except requests.exceptions.ConnectionError:
        return {"exito": False, "error": "Error de conexión con la API de WhatsApp"}
    except Exception as e:
        return {"exito": False, "error": f"Error inesperado: {str(e)}"}