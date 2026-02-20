from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import os
import datetime
from app.db.base import get_db
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
# [CLOUDINARY] Importar el servicio de Cloudinary que creamos
from app.services.cloudinary import subir_imagen_desde_url

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

@router.post("/webhook")
async def webhook_whatsapp(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint que procesa los mensajes de WhatsApp
    """
    try:
        # Obtener el cuerpo de la petición
        body = await request.json()
        print("📩 Mensaje recibido:", body)
        
        # Extraer información del mensaje (formato de Meta WhatsApp Business API)
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "ok", "message": "Sin mensajes"}
        
        # Tomar el primer mensaje
        msg = messages[0]
        telefono_cliente = msg.get("from")
        
        # [CLOUDINARY] Detectar tipo de mensaje (texto, imagen, etc.)
        tipo_mensaje = msg.get("type", "text")
        texto_mensaje = ""
        imagen_info = None
        
        if tipo_mensaje == "text":
            texto_mensaje = msg.get("text", {}).get("body", "")
        elif tipo_mensaje == "image":
            # Extraer información de la imagen
            imagen_data = msg.get("image", {})
            imagen_id = imagen_data.get("id")
            if imagen_id:
                texto_mensaje = "📷 [El cliente envió un comprobante de pago]"
                # [CLOUDINARY] Guardamos info de la imagen para procesar después
                imagen_info = {
                    "id": imagen_id,
                    "mime_type": imagen_data.get("mime_type"),
                    "sha256": imagen_data.get("sha256"),
                    "caption": texto_mensaje
                }
        
        # Número de teléfono de la empresa (quien recibe)
        metadata = value.get("metadata", {})
        telefono_empresa = metadata.get("display_phone_number", "")
        
        if not telefono_cliente or (not texto_mensaje and not imagen_info):
            return {"status": "ok", "message": "Mensaje sin contenido"}
        
        # 1. Identificar empresa por su número de WhatsApp
        empresa = db.query(Empresa).filter(
            Empresa.telefono_whatsapp == telefono_empresa,
            Empresa.activa == True
        ).first()
        
        if not empresa:
            print(f"⚠️ Empresa no encontrada para teléfono: {telefono_empresa}")
            return {"status": "ok", "message": "Empresa no identificada"}
        
        # 2. Buscar o crear cliente
        cliente = db.query(Cliente).filter(
            Cliente.empresa_id == empresa.id,
            Cliente.telefono == telefono_cliente
        ).first()
        
        if not cliente:
            cliente = Cliente(
                empresa_id=empresa.id,
                telefono=telefono_cliente,
                nombre=msg.get("profile", {}).get("name", ""),
                resumen="Cliente nuevo",
                datos_estructurados={}
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        
        # [CLOUDINARY] Si es una imagen, procesarla (esto se implementará después)
        url_comprobante = None
        if imagen_info:
            # TODO: Aquí implementaremos la descarga de la imagen desde WhatsApp
            # y su subida a Cloudinary cuando tengamos el token de acceso
            # Por ahora solo guardamos que recibió una imagen
            datos_cliente = cliente.datos_estructurados or {}
            datos_cliente["ultimo_comprobante"] = {
                "recibido": True,
                "fecha": str(datetime.now()),
                "tipo": imagen_info["mime_type"]
            }
            cliente.datos_estructurados = datos_cliente
            db.commit()
        
        # 3. Guardar mensaje del cliente
        mensaje_cliente = Conversacion(
            cliente_id=cliente.id,
            mensaje=texto_mensaje,
            emisor=TipoEmisor.CLIENTE
        )
        db.add(mensaje_cliente)
        db.commit()
        
        # 4. Inicializar servicios
        rag = RAGService(db, empresa.id, cliente.id)
        memoria = MemoriaService(db, cliente.id)
        
        # 5. Obtener resumen del cliente
        resumen_cliente = memoria.obtener_resumen()
        
        # 6. Buscar documentos relevantes (RAG)
        documentos_relevantes = rag.buscar_similares(texto_mensaje, top_k=3)
        contexto = "\n\n".join([doc["texto"] for doc in documentos_relevantes])
        
        # 7. Generar respuesta con LLM
        respuesta_texto = rag.generar_respuesta_llm(
            consulta=texto_mensaje,
            contexto=contexto,
            resumen_cliente=resumen_cliente
        )
        
        # [CLOUDINARY] Si era un comprobante, personalizar la respuesta
        if imagen_info:
            respuesta_texto = "✅ ¡Gracias por enviar tu comprobante! Hemos recibido la imagen correctamente. Un asesor verificará el pago y te dará acceso al curso en las próximas horas. 😊"
        
        # 8. Guardar respuesta del bot
        mensaje_bot = Conversacion(
            cliente_id=cliente.id,
            mensaje=respuesta_texto,
            emisor=TipoEmisor.BOT
        )
        db.add(mensaje_bot)
        db.commit()
        
        # 9. Actualizar memoria del cliente
        memoria.actualizar_resumen(texto_mensaje, respuesta_texto)
        
        # 10. Aquí enviarías la respuesta a WhatsApp usando la API de Meta
        # Por ahora solo devolvemos la respuesta para pruebas
        return {
            "status": "ok",
            "respuesta": respuesta_texto,
            "cliente_id": cliente.id,
            "documentos_usados": len(documentos_relevantes),
            "tipo_mensaje": tipo_mensaje,
            "imagen_procesada": imagen_info is not None
        }
        
    except Exception as e:
        print(f"❌ Error procesando webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/webhook")
async def verificar_webhook(request: Request):
    """
    Endpoint para verificación inicial del webhook de Meta
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_token_secreto")
    
    if mode and token:
        if mode == "subscribe" and token == verify_token:
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verificación fallida")
    
    return {"status": "ok"}