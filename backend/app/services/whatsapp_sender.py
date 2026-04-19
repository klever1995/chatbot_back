import os
import httpx
from typing import Optional, List, Dict, Any

async def enviar_mensaje_whatsapp(
    telefono_destino: str,
    mensaje: str,
    token: str,
    phone_number_id: str
) -> dict:
    """
    Envía un mensaje de texto a un número de WhatsApp usando la API de Meta (asíncrono)
    
    Args:
        telefono_destino: Número de teléfono del destinatario (con código de país)
        mensaje: Texto del mensaje a enviar
        token: Token de acceso de la empresa
        phone_number_id: ID del número de WhatsApp de la empresa
    
    Returns:
        dict: Respuesta de la API de Meta o información del error
    """
    if not token:
        return {
            "exito": False,
            "error": "No hay token de acceso configurado para esta empresa"
        }
    
    if not phone_number_id:
        return {
            "exito": False,
            "error": "No hay phone_number_id configurado para esta empresa"
        }
    
    # URL base de la API de Meta usando el phone_number_id de la empresa
    base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    # Cabeceras de la petición
    headers = {
        "Authorization": f"Bearer {token}",
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
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(base_url, headers=headers, json=payload)
        
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
            
    except httpx.TimeoutException:
        return {
            "exito": False,
            "error": "Timeout al conectar con la API de WhatsApp"
        }
    except httpx.ConnectError:
        return {
            "exito": False,
            "error": "Error de conexión con la API de WhatsApp"
        }
    except Exception as e:
        return {
            "exito": False,
            "error": f"Error inesperado: {str(e)}"
        }

async def enviar_mensaje_con_plantilla(
    telefono_destino: str,
    nombre_plantilla: str,
    token: str,
    phone_number_id: str,
    componentes: list = []
) -> dict:
    """
    Envía un mensaje usando una plantilla aprobada (útil para notificaciones) - asíncrono
    
    Args:
        telefono_destino: Número de teléfono del destinatario
        nombre_plantilla: Nombre de la plantilla en Meta
        token: Token de acceso de la empresa
        phone_number_id: ID del número de WhatsApp de la empresa
        componentes: Componentes de la plantilla (cabecera, cuerpo, botones)
    
    Returns:
        dict: Respuesta de la API
    """
    if not token:
        return {"exito": False, "error": "No hay token configurado para esta empresa"}
    
    if not phone_number_id:
        return {"exito": False, "error": "No hay phone_number_id configurado para esta empresa"}
    
    base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
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
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(base_url, headers=headers, json=payload)
        
        if response.status_code == 200 or response.status_code == 201:
            return {"exito": True, "data": response.json()}
        else:
            return {"exito": False, "error": f"Error {response.status_code}", "detalles": response.json()}
            
    except Exception as e:
        return {"exito": False, "error": f"Error: {str(e)}"}

async def enviar_mensaje_con_botones(
    telefono_destino: str,
    texto_cabecera: str,
    cliente_id: int,
    token: str,
    phone_number_id: str
) -> dict:
    """
    Envía un mensaje con botones interactivos de aprobar/rechazar - asíncrono
    
    Args:
        telefono_destino: Número del destinatario (dueño)
        texto_cabecera: Texto informativo sobre el cliente/comprobante
        cliente_id: ID del cliente para incluir en el callback_data
        token: Token de acceso de la empresa
        phone_number_id: ID del número de WhatsApp de la empresa
    
    Returns:
        dict: Respuesta de la API
    """
    if not token:
        return {"exito": False, "error": "No hay token configurado para esta empresa"}
    
    if not phone_number_id:
        return {"exito": False, "error": "No hay phone_number_id configurado para esta empresa"}
    
    base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
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
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(base_url, headers=headers, json=payload)
        
        if response.status_code == 200 or response.status_code == 201:
            return {"exito": True, "data": response.json()}
        else:
            return {"exito": False, "error": f"Error {response.status_code}", "detalles": response.json()}
            
    except httpx.TimeoutException:
        return {"exito": False, "error": "Timeout al conectar con la API de WhatsApp"}
    except httpx.ConnectError:
        return {"exito": False, "error": "Error de conexión con la API de WhatsApp"}
    except Exception as e:
        return {"exito": False, "error": f"Error inesperado: {str(e)}"}