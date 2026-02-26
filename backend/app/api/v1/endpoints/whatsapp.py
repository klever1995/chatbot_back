from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import os
import datetime
import requests
import re
from groq import Groq
from app.db.base import get_db
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.cloudinary import subir_imagen_desde_bytes
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

def transcribir_audio(url_audio: str) -> str:
    """Transcribe audio usando Groq Whisper desde URL directa"""
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        headers = {"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}"}
        response = requests.get(url_audio, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Error descargando audio: {response.status_code}")
        
        archivo = ("audio.ogg", response.content, "audio/ogg")
        
        transcripcion = client.audio.transcriptions.create(
            file=archivo,
            model="whisper-large-v3",
            response_format="text"
        )
        
        return transcripcion
    except Exception as e:
        print(f"❌ Error en transcripción con Groq: {type(e).__name__}: {str(e)}")
        return "[Error al transcribir el audio]"

@router.post("/webhook")
async def webhook_whatsapp(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint que procesa los mensajes de WhatsApp
    """
    try:
        body = await request.json()
        print("📩 Mensaje recibido:", body)
        
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "ok", "message": "Sin mensajes"}
        
        msg = messages[0]
        telefono_cliente = msg.get("from")
        
        tipo_mensaje = msg.get("type", "text")
        texto_mensaje = ""
        imagen_info = None
        audio_url = None
        
        # Detectar tipo de mensaje
        if tipo_mensaje == "text":
            texto_mensaje = msg.get("text", {}).get("body", "")
        elif tipo_mensaje == "image":
            imagen_data = msg.get("image", {})
            imagen_id = imagen_data.get("id")
            if imagen_id:
                texto_mensaje = "📷 [El cliente envió un comprobante de pago]"
                imagen_info = {
                    "id": imagen_id,
                    "mime_type": imagen_data.get("mime_type"),
                    "sha256": imagen_data.get("sha256"),
                    "url": imagen_data.get("url")
                }
        elif tipo_mensaje == "audio":
            audio_data = msg.get("audio", {})
            audio_url = audio_data.get("url")
            if audio_url:
                texto_mensaje = "🎤 [El cliente envió un audio]"
        # 👇 NUEVO: DETECTAR RESPUESTA DE BOTONES INTERACTIVOS
        elif tipo_mensaje == "interactive":
            interactive_data = msg.get("interactive", {})
            if interactive_data.get("type") == "button_reply":
                button_reply = interactive_data.get("button_reply", {})
                texto_mensaje = f"🔘 [Respuesta de botón: {button_reply.get('title')}]"
                # Guardamos el callback_data para procesarlo después
                msg["callback_data"] = button_reply.get("id")
        
        metadata = value.get("metadata", {})
        telefono_empresa = metadata.get("display_phone_number", "")
        telefono_empresa = telefono_empresa.replace("+", "")
        
        if not telefono_cliente or (not texto_mensaje and not imagen_info and not audio_url):
            return {"status": "ok", "message": "Mensaje sin contenido"}
        
        empresa = db.query(Empresa).filter(
            Empresa.telefono_whatsapp == telefono_empresa,
            Empresa.activa == True
        ).first()
        
        if not empresa:
            print(f"⚠️ Empresa no encontrada para teléfono: {telefono_empresa}")
            return {"status": "ok", "message": "Empresa no identificada"}
        
        cliente = db.query(Cliente).filter(
            Cliente.empresa_id == empresa.id,
            Cliente.telefono == telefono_cliente
        ).first()
        
        # 👇 PROCESAR RESPUESTAS DEL DUEÑO (tanto texto como botones)
        if empresa.telefono_dueño and telefono_cliente == empresa.telefono_dueño:
            
            # Procesar respuesta de botones (callback_data)
            if tipo_mensaje == "interactive" and msg.get("callback_data"):
                callback_id = msg.get("callback_data")
                
                if callback_id.startswith("APROBAR_") or callback_id.startswith("RECHAZAR_"):
                    partes = callback_id.split("_")
                    accion = partes[0]
                    cliente_id = int(partes[1])
                    
                    cliente_pendiente = db.query(Cliente).filter(
                        Cliente.id == cliente_id,
                        Cliente.empresa_id == empresa.id
                    ).first()
                    
                    if cliente_pendiente and cliente_pendiente.datos_estructurados:
                        datos = cliente_pendiente.datos_estructurados
                        if datos.get("ultimo_comprobante", {}).get("estado_pago") == "pendiente":
                            
                            if accion == "APROBAR":
                                datos["ultimo_comprobante"]["estado_pago"] = "confirmado"
                                datos["ultimo_comprobante"]["fecha_confirmacion"] = str(datetime.datetime.now())
                                
                                mensaje_confirmacion = "✅ ¡Buenas noticias! Tu pago ha sido verificado y ya tienes acceso al curso. 😊"
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_confirmacion)
                                
                                mensaje_material = (
                                    "✅ ¡Gracias por tu paciencia! Tu material de LETTERING ya está listo. Aquí tienes el acceso para descargarlo:\n\n"
                                    "[Acceso al Pack de Lettering](https://drive.google.com/drive/folders/1o1281qJnphKE3ClYHSHw1vNg6U?usp=shar)\n\n"
                                    "Incluye:\n"
                                    "- Guías y libros digitales\n"
                                    "- Plantillas de práctica\n"
                                    "- Cuadernillo de caligrafía\n"
                                    "- Técnicas y secretos para mejorar tus diseños\n\n"
                                    "Todo es digital (PDF) y tendrás acceso de por vida. Si necesitas ayuda con algo o tienes dudas, no dudes en escribirme. ¡Gracias por tu compra y disfruta de tu aventura creativa! 😊"
                                )
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_material)
                                
                            else:  # RECHAZAR
                                datos["ultimo_comprobante"]["estado_pago"] = "rechazado"
                                datos["ultimo_comprobante"]["fecha_rechazo"] = str(datetime.datetime.now())
                                mensaje_rechazo = "❌ Hubo un problema con tu comprobante. Por favor, contacta a un asesor para más detalles."
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_rechazo)
                            
                            cliente_pendiente.datos_estructurados = datos
                            db.commit()
                            
                            return {"status": "ok", "message": f"Pago {accion} para cliente {cliente_id}"}
            
            # Procesar comandos de texto (respaldo, pero ya no se usa)
            match = re.search(r"(APROBAR|RECHAZAR)\s+(\d+)", texto_mensaje.upper())
            if match:
                accion = match.group(1)
                cliente_id = int(match.group(2))
                
                cliente_pendiente = db.query(Cliente).filter(
                    Cliente.id == cliente_id,
                    Cliente.empresa_id == empresa.id
                ).first()
                
                if cliente_pendiente and cliente_pendiente.datos_estructurados:
                    datos = cliente_pendiente.datos_estructurados
                    if datos.get("ultimo_comprobante", {}).get("estado_pago") == "pendiente":
                        
                        if accion == "APROBAR":
                            datos["ultimo_comprobante"]["estado_pago"] = "confirmado"
                            datos["ultimo_comprobante"]["fecha_confirmacion"] = str(datetime.datetime.now())
                            
                            mensaje_confirmacion = "✅ ¡Buenas noticias! Tu pago ha sido verificado y ya tienes acceso al curso. 😊"
                            enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_confirmacion)
                            
                            mensaje_material = (
                                "✅ ¡Gracias por tu paciencia! Tu material de LETTERING ya está listo. Aquí tienes el acceso para descargarlo:\n\n"
                                "[Acceso al Pack de Lettering](https://drive.google.com/drive/folders/1o1281qJnphKE3ClYHSHw1vNg6U?usp=shar)\n\n"
                                "Incluye:\n"
                                "- Guías y libros digitales\n"
                                "- Plantillas de práctica\n"
                                "- Cuadernillo de caligrafía\n"
                                "- Técnicas y secretos para mejorar tus diseños\n\n"
                                "Todo es digital (PDF) y tendrás acceso de por vida. Si necesitas ayuda con algo o tienes dudas, no dudes en escribirme. ¡Gracias por tu compra y disfruta de tu aventura creativa! 😊"
                            )
                            enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_material)
                            
                        else:  # RECHAZAR
                            datos["ultimo_comprobante"]["estado_pago"] = "rechazado"
                            datos["ultimo_comprobante"]["fecha_rechazo"] = str(datetime.datetime.now())
                            mensaje_rechazo = "❌ Hubo un problema con tu comprobante. Por favor, contacta a un asesor para más detalles."
                            enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_rechazo)
                        
                        cliente_pendiente.datos_estructurados = datos
                        db.commit()
                        
                        return {"status": "ok", "message": f"Pago {accion} para cliente {cliente_id}"}
            
            return {"status": "ok", "message": "Comando no reconocido o cliente sin pago pendiente"}
        
        # Crear cliente si no existe
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
        
        # Procesar audio si existe
        if audio_url:
            try:
                transcripcion = transcribir_audio(audio_url)
                texto_mensaje = f"🎤 [Audio transcrito]: {transcripcion}"
                print(f"📝 Transcripción: {transcripcion}")
            except Exception as e:
                print(f"❌ Error procesando audio: {e}")
                texto_mensaje = "🎤 [Error al procesar el audio]"
        
        # Procesar imagen (comprobante)
        url_comprobante = None
        if imagen_info:
            try:
                url_imagen_whatsapp = imagen_info.get("url")
                whatsapp_token = os.getenv("WHATSAPP_TOKEN")
                
                if not url_imagen_whatsapp:
                    raise Exception("No se recibió URL de la imagen")
                
                headers = {"Authorization": f"Bearer {whatsapp_token}"}
                response = requests.get(url_imagen_whatsapp, headers=headers)
                
                if response.status_code == 200:
                    public_id_gen = f"comprobante_{cliente.id}_{int(datetime.datetime.now().timestamp())}"
                    resultado_cloudinary = subir_imagen_desde_bytes(
                        response.content, 
                        public_id=public_id_gen
                    )
                    
                    if resultado_cloudinary:
                        url_comprobante = resultado_cloudinary["url"]
                        datos_cliente = cliente.datos_estructurados or {}
                        datos_cliente["ultimo_comprobante"] = {
                            "url": url_comprobante,
                            "fecha": str(datetime.datetime.now()),
                            "estado_pago": "pendiente",
                            "tipo": imagen_info["mime_type"]
                        }
                        cliente.datos_estructurados = datos_cliente
                        db.commit()
                        
                        # Enviar notificación al dueño con botones
                        if empresa.telefono_dueño:
                            texto_cabecera = (
                                f"🔔 *NUEVO COMPROBANTE*\n\n"
                                f"*Cliente:* {cliente.nombre or 'Desconocido'}\n"
                                f"*Teléfono:* {cliente.telefono}\n"
                                f"*Comprobante:* {url_comprobante}"
                            )
                            enviar_mensaje_con_botones(
                                telefono_destino=empresa.telefono_dueño,
                                texto_cabecera=texto_cabecera,
                                cliente_id=cliente.id
                            )
                else:
                    print(f"❌ Falló descarga de Meta: {response.status_code}")
                        
            except Exception as e:
                print(f"❌ Error procesando imagen: {e}")
        
        # Guardar mensaje del cliente
        mensaje_cliente = Conversacion(
            cliente_id=cliente.id,
            mensaje=texto_mensaje,
            emisor=TipoEmisor.CLIENTE
        )
        db.add(mensaje_cliente)
        db.commit()
        
        # Inicializar servicios
        rag = RAGService(db, empresa.id, cliente.id)
        memoria = MemoriaService(db, cliente.id)
        
        # RAG y generación de respuesta
        resumen_cliente = memoria.obtener_resumen()
        documentos_relevantes = rag.buscar_similares(texto_mensaje, top_k=3)
        contexto = "\n\n".join([doc["texto"] for doc in documentos_relevantes])
        
        respuesta_texto = rag.generar_respuesta_llm(
            consulta=texto_mensaje,
            contexto=contexto,
            resumen_cliente=resumen_cliente
        )
        
        if imagen_info:
            respuesta_texto = "✅ ¡Gracias por enviar tu comprobante! Hemos notificado al asesor. En breve recibirás la confirmación. 😊"
        elif audio_url:
            respuesta_texto = f"🎤 He recibido tu audio. {respuesta_texto}"
        
        # Guardar respuesta del bot
        mensaje_bot = Conversacion(
            cliente_id=cliente.id,
            mensaje=respuesta_texto,
            emisor=TipoEmisor.BOT
        )
        db.add(mensaje_bot)
        db.commit()
        
        # Enviar respuesta al cliente
        enviar_mensaje_whatsapp(
            telefono_destino=telefono_cliente,
            mensaje=respuesta_texto
        )
        
        # Actualizar memoria
        memoria.actualizar_resumen(texto_mensaje, respuesta_texto)
        
        return {"status": "ok", "cliente_id": cliente.id}
        
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
    
    if mode == "subscribe" and token == verify_token:
        return int(challenge)
    
    raise HTTPException(status_code=403, detail="Verificación fallida")