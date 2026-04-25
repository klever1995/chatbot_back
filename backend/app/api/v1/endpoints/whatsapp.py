from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import os
import datetime
import requests
import re
import json
from groq import Groq
from app.db.base import get_db
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.documento import Documento
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.cloudinary import subir_imagen_desde_bytes
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones
from app.handlers.venta_unica_handler import procesar_mensaje_venta_unica, procesar_comprobante_venta_unica, aprobar_venta_unica
from app.handlers.pedido_handler import responder_pregunta_restaurante, procesar_comprobante_pedido, aprobar_pedido
from app.handlers.informativo_handler import responder_pregunta_informativo

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

def transcribir_audio(url_audio: str, groq_api_key: str, whatsapp_token: str) -> str:
    """Transcribe audio usando Groq Whisper desde URL directa"""
    try:
        client = Groq(api_key=groq_api_key)
        
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
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
        # Comentado para limpiar la terminal: print("📩 Mensaje recibido:", body)
        
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        # 🔥 NUEVO: Ignorar webhooks que no contengan mensajes de usuario (solo statuses)
        if not messages:
            # Verificar si hay statuses para no imprimir innecesariamente
            if "statuses" not in value:
                print("📩 Webhook sin mensajes ni statuses")
            return {"status": "ok", "message": "Sin mensajes"}
        
        msg = messages[0]
        
        # SOLUCIÓN: Validación de timestamp para ignorar mensajes antiguos (más de 30 segundos)
        timestamp_msg = int(msg.get("timestamp", 0))
        timestamp_actual = int(datetime.datetime.now().timestamp())
        if timestamp_actual - timestamp_msg > 30:
            print(f"⏰ Mensaje antiguo ignorado: timestamp={timestamp_msg}, actual={timestamp_actual}")
            return {"status": "ok", "message": "Mensaje antiguo ignorado"}
        
        telefono_cliente = msg.get("from")
        
        # 🔥 IDENTIFICAR EMPRESA POR PHONE_NUMBER_ID O DISPLAY_PHONE_NUMBER
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")
        telefono_empresa = metadata.get("display_phone_number", "")
        telefono_empresa = telefono_empresa.replace("+", "")
        
        # Buscar empresa por phone_number_id o por telefono_whatsapp
        empresa = None
        if phone_number_id:
            empresa = db.query(Empresa).filter(
                Empresa.phone_number_id == phone_number_id,
                Empresa.activa == True
            ).first()
        
        if not empresa and telefono_empresa:
            empresa = db.query(Empresa).filter(
                Empresa.telefono_whatsapp == telefono_empresa,
                Empresa.activa == True
            ).first()
        
        if not empresa:
            print(f"⚠️ Empresa no encontrada para phone_number_id: {phone_number_id} o teléfono: {telefono_empresa}")
            return {"status": "ok", "message": "Empresa no identificada"}
        
        # 🔥 EXTRAER CREDENCIALES DE LA EMPRESA
        whatsapp_token = empresa.whatsapp_token
        groq_api_key = empresa.groq_api_key
        phone_number_id = empresa.phone_number_id
        
        tipo_mensaje = msg.get("type", "text")
        texto_mensaje = ""
        imagen_info = None
        audio_url = None
        
        # Detectar tipo de mensaje
        if tipo_mensaje == "text":
            texto_mensaje = msg.get("text", {}).get("body", "")
            print(f"📝 Texto recibido: '{texto_mensaje}'")
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
        elif tipo_mensaje == "interactive":
            interactive_data = msg.get("interactive", {})
            if interactive_data.get("type") == "button_reply":
                button_reply = interactive_data.get("button_reply", {})
                texto_mensaje = f"🔘 [Respuesta de botón: {button_reply.get('title')}]"
                msg["callback_data"] = button_reply.get("id")
        
        # Detectar campaña desde el primer mensaje
        campania_detectada = None
        if tipo_mensaje == "text" and texto_mensaje:
            print(f"🔍 Evaluando si es campaña: '{texto_mensaje}'")
            
            if texto_mensaje.startswith("campaña_"):
                print("✅ ¡Empieza con 'campaña_'!")
                partes = texto_mensaje.split("_", 1)
                if len(partes) > 1:
                    campania_detectada = partes[1].strip().lower()
                    print(f"🎯 CAMPAÑA DETECTADA: '{campania_detectada}'")
                    texto_mensaje = ""
            
            elif "campaña=" in texto_mensaje:
                print("✅ ¡Contiene 'campaña='!")
                match = re.search(r'campaña=(\w+)', texto_mensaje)
                if match:
                    campania_detectada = match.group(1).strip().lower()
                    print(f"🎯 CAMPAÑA DETECTADA: '{campania_detectada}'")
                    texto_mensaje = re.sub(r'campaña=\w+\s*', '', texto_mensaje).strip()
            else:
                print("❌ No es un mensaje de campaña")
        
        if not telefono_cliente or (not texto_mensaje and not imagen_info and not audio_url and not campania_detectada):
            return {"status": "ok", "message": "Mensaje sin contenido"}
        
        # Buscar cliente existente
        print(f"🔍 Buscando cliente con teléfono: {telefono_cliente}")
        cliente = db.query(Cliente).filter(
            Cliente.empresa_id == empresa.id,
            Cliente.telefono == telefono_cliente
        ).first()
        
        if cliente:
            print(f"👤 Cliente existente encontrado. Datos actuales: {cliente.datos_estructurados}")
        else:
            print("👤 Cliente no existe, se creará uno nuevo")
        
        # PROCESAR RESPUESTAS DEL DUEÑO
        if empresa.telefono_dueño and telefono_cliente == empresa.telefono_dueño:
            
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
                        # Determinar si es pedido múltiple o venta única
                        campania_cliente = cliente_pendiente.datos_estructurados.get("campania_activa")
                        es_restaurante = False
                        if campania_cliente:
                            doc_campania = db.query(Documento).filter(
                                Documento.empresa_id == empresa.id,
                                Documento.campania_id == campania_cliente
                            ).first()
                            if doc_campania and doc_campania.tipo_campania == "pedido_multiple":
                                es_restaurante = True
                        
                        if es_restaurante:
                            # Aprobar pedido múltiple
                            await aprobar_pedido(db, empresa, cliente_pendiente, accion, whatsapp_token, phone_number_id)
                        else:
                            # Aprobar venta única
                            datos = cliente_pendiente.datos_estructurados
                            if datos.get("ultimo_comprobante", {}).get("estado_pago") == "pendiente":
                                if accion == "APROBAR":
                                    await aprobar_venta_unica(db, empresa, cliente_pendiente, "APROBAR", whatsapp_token, phone_number_id)
                                else:
                                    await aprobar_venta_unica(db, empresa, cliente_pendiente, "RECHAZAR", whatsapp_token, phone_number_id)
                        
                        return {"status": "ok", "message": f"Pago {accion} para cliente {cliente_id}"}
            
            return {"status": "ok", "message": "Formato no reconocido o cliente sin pago pendiente"}
        
        # Guardar/Actualizar cliente con campaña y limpiar historial
        if not cliente:
            datos_iniciales = {}
            if campania_detectada:
                datos_iniciales["campania_activa"] = campania_detectada
                print(f"✅ GUARDANDO: Campaña {campania_detectada} en cliente NUEVO {telefono_cliente}")
            
            cliente = Cliente(
                empresa_id=empresa.id,
                telefono=telefono_cliente,
                nombre=msg.get("profile", {}).get("name", ""),
                resumen="Cliente nuevo",
                datos_estructurados=datos_iniciales
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
            print(f"🆔 Cliente creado con ID: {cliente.id}, datos: {cliente.datos_estructurados}")
            
            if campania_detectada:
                conversaciones_eliminadas = db.query(Conversacion).filter(
                    Conversacion.cliente_id == cliente.id
                ).delete(synchronize_session=False)
                db.commit()
                print(f"🧹 Historial limpiado para cliente nuevo: {conversaciones_eliminadas} mensajes eliminados")
                
        else:
            if campania_detectada:
                print(f"🔄 ACTUALIZANDO: Cliente existente. Campaña detectada: {campania_detectada}")
                
                datos = cliente.datos_estructurados or {}
                datos["campania_activa"] = campania_detectada
                cliente.datos_estructurados = datos
                
                # 🔥 LIMPIAR HISTORIAL PARA PEDIDOS MÚLTIPLES TAMBIÉN (igual que ventas individuales)
                conversaciones_eliminadas = db.query(Conversacion).filter(
                    Conversacion.cliente_id == cliente.id
                ).delete(synchronize_session=False)
                
                cliente.resumen = f"Cliente nuevo - campaña {campania_detectada}"
                
                db.commit()
                db.refresh(cliente)
                print(f"✅ Campaña actualizada. Datos ahora: {cliente.datos_estructurados}")
                print(f"🧹 Historial limpiado: {conversaciones_eliminadas} mensajes eliminados para cliente {cliente.id}")
            else:
                print(f"ℹ️ Cliente existente sin nueva campaña. Datos actuales: {cliente.datos_estructurados}")
        
        # Procesar audio si existe
        if audio_url:
            try:
                transcripcion = transcribir_audio(audio_url, groq_api_key, whatsapp_token)
                texto_mensaje = f"🎤 [Audio transcrito]: {transcripcion}"
                print(f"📝 Transcripción: {transcripcion}")
            except Exception as e:
                print(f"❌ Error procesando audio: {e}")
                texto_mensaje = "🎤 [Error al procesar el audio]"
        
        # Verificar el tipo de campaña del documento
        campania_activa = None
        if cliente.datos_estructurados:
            campania_activa = cliente.datos_estructurados.get("campania_activa")
        
        tipo_campania = "producto_unico"  # valor por defecto
        if campania_activa:
            documento_campania = db.query(Documento).filter(
                Documento.empresa_id == empresa.id,
                Documento.campania_id == campania_activa
            ).first()
            if documento_campania:
                tipo_campania = documento_campania.tipo_campania or "producto_unico"
        
        es_restaurante = (tipo_campania == "pedido_multiple")
        es_informativo = (tipo_campania == "informativo")
        
        # Procesar imagen (comprobante)
        url_comprobante = None
        if imagen_info:
            try:
                url_imagen_whatsapp = imagen_info.get("url")
                
                if not url_imagen_whatsapp:
                    raise Exception("No se recibió URL de la imagen")
                
                headers = {"Authorization": f"Bearer {whatsapp_token}"}
                response = requests.get(url_imagen_whatsapp, headers=headers)
                
                if response.status_code == 200:
                    public_id_gen = f"comprobante_{cliente.id}_{int(datetime.datetime.now().timestamp())}"
                    resultado_cloudinary = subir_imagen_desde_bytes(
                        response.content,
                        cloud_name=empresa.cloudinary_cloud_name,
                        api_key=empresa.cloudinary_api_key,
                        api_secret=empresa.cloudinary_api_secret,
                        public_id=public_id_gen
                    )
                    
                    if resultado_cloudinary:
                        url_comprobante = resultado_cloudinary["url"]
                        
                        if es_restaurante:
                            print(f"\n🔍🔍🔍 DEBUG INICIO - PROCESAMIENTO COMPROBANTE RESTAURANTE 🔍🔍🔍")
                            print(f"🔍 DEBUG: cliente.id = {cliente.id}")
                            print(f"🔍 DEBUG: campania_activa = {campania_activa}")
                            print(f"🔍 DEBUG: empresa.id = {empresa.id}")
                            
                            # Obtener TODOS los mensajes de la conversación (cliente y bot) desde que se activó la campaña
                            mensajes_conversacion = db.query(Conversacion).filter(
                                Conversacion.cliente_id == cliente.id
                            ).order_by(Conversacion.timestamp.asc()).all()
                            
                            print(f"🔍 DEBUG: mensajes_conversacion encontrados = {len(mensajes_conversacion)}")
                            for i, m in enumerate(mensajes_conversacion):
                                print(f"  DEBUG mensaje {i+1}: emisor={m.emisor.value}, texto={m.mensaje[:100]}")
                            
                            # Unir todos los mensajes en un solo texto con el formato "Cliente: ..." o "Bot: ..."
                            historial_completo = "\n".join([f"{'Cliente' if msg.emisor == TipoEmisor.CLIENTE else 'Bot'}: {msg.mensaje}" for msg in mensajes_conversacion])
                            
                            print(f"🔍 DEBUG: historial_completo LENGTH = {len(historial_completo)} caracteres")
                            print(f"🔍 DEBUG: historial_completo CONTENIDO:\n{historial_completo}")
                            
                            # Usar LLM para extraer el pedido y el total del historial completo
                            from openai import OpenAI
                            client_openai = OpenAI(api_key=empresa.openai_api_key)
                            
                            prompt_extractor = f"""
                            Extrae el pedido y el monto total de la siguiente conversación entre el cliente y el bot:
                            
                            {historial_completo}
                            
                            Devuelve SOLO un JSON con esta estructura:
                            {{
                                "texto_pedido": "resumen del pedido",
                                "monto_total": numero
                            }}
                            
                            Si no hay un pedido claro, devuelve monto_total 0.
                            """
                            
                            print(f"🔍 DEBUG: prompt_extractor (primeros 500 chars): {prompt_extractor[:500]}...")
                            
                            respuesta_llm = client_openai.chat.completions.create(
                                model=empresa.openai_chat_model or "gpt-4o",
                                messages=[{"role": "user", "content": prompt_extractor}],
                                temperature=0.2
                            )
                            
                            contenido = respuesta_llm.choices[0].message.content
                            print(f"🔍 DEBUG: respuesta_llm RAW = {contenido}")
                            
                            contenido = re.sub(r'```json\n?', '', contenido)
                            contenido = re.sub(r'```\n?', '', contenido)
                            
                            try:
                                datos_pedido = json.loads(contenido)
                                texto_pedido = datos_pedido.get("texto_pedido", "No se pudo determinar el pedido")
                                monto_total = float(datos_pedido.get("monto_total", 0))
                                print(f"🔍 DEBUG: texto_pedido extraído = {texto_pedido}")
                                print(f"🔍 DEBUG: monto_total extraído = {monto_total}")
                            except Exception as e:
                                print(f"🔍 DEBUG: ERROR parseando JSON: {e}")
                                texto_pedido = "No se pudo determinar el pedido"
                                monto_total = 0
                            
                            print(f"🔍🔍🔍 DEBUG FIN - llamando a procesar_comprobante_pedido 🔍🔍🔍")
                            
                            await procesar_comprobante_pedido(
                                db, empresa, cliente, url_comprobante, imagen_info, texto_pedido, monto_total, whatsapp_token, phone_number_id
                            )
                        else:
                            await procesar_comprobante_venta_unica(db, empresa, cliente, url_comprobante, imagen_info, whatsapp_token, phone_number_id)
                else:
                    print(f"❌ Falló descarga de Meta: {response.status_code}")
                        
            except Exception as e:
                print(f"❌ Error procesando imagen: {e}")
        
        # Guardar mensaje del cliente (solo si hay contenido)
        if texto_mensaje:
            mensaje_cliente = Conversacion(
                cliente_id=cliente.id,
                mensaje=texto_mensaje,
                emisor=TipoEmisor.CLIENTE
            )
            db.add(mensaje_cliente)
            db.commit()
            print(f"💬 Mensaje guardado: {texto_mensaje[:50]}...")
        else:
            print("⏸️ No hay mensaje de texto, esperando siguiente interacción")
            return {"status": "ok", "message": "Parámetro de campaña recibido, esperando mensaje del cliente"}
        
        # Redirigir según el tipo de campaña
        if es_informativo:
            # Documento informativo: solo responde preguntas usando RAG
            await responder_pregunta_informativo(
                db, empresa, cliente, texto_mensaje, campania_activa, whatsapp_token, phone_number_id
            )
        elif es_restaurante and not imagen_info:
            # Pedido múltiple: solo responde preguntas si no es una imagen
            await responder_pregunta_restaurante(
                db, empresa, cliente, texto_mensaje, campania_activa, whatsapp_token, phone_number_id
            )
        elif es_restaurante and imagen_info:
            # Ya se procesó el comprobante, no hacemos nada más
            print("📷 Comprobante ya procesado, no se envía respuesta adicional")
        else:
            # Producto único: flujo normal de venta individual
            await procesar_mensaje_venta_unica(
                db, empresa, cliente, texto_mensaje, imagen_info, audio_url, campania_activa, whatsapp_token, phone_number_id
            )
        
        return {"status": "ok", "cliente_id": cliente.id}
        
    except Exception as e:
        print(f"❌ Error procesando webhook: {str(e)}")
        import traceback
        traceback.print_exc()
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