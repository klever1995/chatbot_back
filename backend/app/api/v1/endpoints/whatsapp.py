from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import os
import datetime
import requests
from groq import Groq
from app.db.base import get_db
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.documento import Documento
from app.models.ventas import Venta, EstadoVenta  # 🔥 IMPORTAR MODELO VENTA
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.cloudinary import subir_imagen_desde_bytes
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones
from app.socket_manager import emitir_nueva_venta

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
            
            # Formato 1: campaña_reposteria
            if texto_mensaje.startswith("campaña_"):
                print("✅ ¡Empieza con 'campaña_'!")
                partes = texto_mensaje.split("_", 1)
                print(f"📌 Partes: {partes}")
                if len(partes) > 1:
                    campania_detectada = partes[1].strip().lower()
                    print(f"🎯 CAMPAÑA DETECTADA: '{campania_detectada}'")
                    texto_mensaje = ""
            
            # Formato 2: campaña=reposteria
            elif "campaña=" in texto_mensaje:
                print("✅ ¡Contiene 'campaña='!")
                import re
                match = re.search(r'campaña=(\w+)', texto_mensaje)
                if match:
                    campania_detectada = match.group(1).strip().lower()
                    print(f"🎯 CAMPAÑA DETECTADA: '{campania_detectada}'")
                    texto_mensaje = re.sub(r'campaña=\w+\s*', '', texto_mensaje).strip()
            else:
                print("❌ No es un mensaje de campaña")
        
        metadata = value.get("metadata", {})
        telefono_empresa = metadata.get("display_phone_number", "")
        telefono_empresa = telefono_empresa.replace("+", "")
        
        if not telefono_cliente or (not texto_mensaje and not imagen_info and not audio_url and not campania_detectada):
            return {"status": "ok", "message": "Mensaje sin contenido"}
        
        empresa = db.query(Empresa).filter(
            Empresa.telefono_whatsapp == telefono_empresa,
            Empresa.activa == True
        ).first()
        
        if not empresa:
            print(f"⚠️ Empresa no encontrada para teléfono: {telefono_empresa}")
            return {"status": "ok", "message": "Empresa no identificada"}
        
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
                        datos = cliente_pendiente.datos_estructurados
                        if datos.get("ultimo_comprobante", {}).get("estado_pago") == "pendiente":
                            
                            if accion == "APROBAR":
                                datos["ultimo_comprobante"]["estado_pago"] = "confirmado"
                                datos["ultimo_comprobante"]["fecha_confirmacion"] = str(datetime.datetime.now())
                                
                                mensaje_confirmacion = "✅ ¡Buenas noticias! Tu pago ha sido verificado y ya tienes acceso al curso. 😊"
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_confirmacion)
                                
                                # 🔥 Obtener campaña activa del cliente
                                campania_cliente = None
                                if cliente_pendiente.datos_estructurados:
                                    campania_cliente = cliente_pendiente.datos_estructurados.get("campania_activa")
                                
                                print(f"📦 Buscando mensaje de entrega para campaña: {campania_cliente}")
                                
                                # Consultar documento para obtener mensaje_entrega y precio
                                documento = db.query(Documento).filter(
                                    Documento.empresa_id == empresa.id,
                                    Documento.campania_id == campania_cliente
                                ).first()
                                
                                if documento and documento.mensaje_entrega:
                                    mensaje_material = documento.mensaje_entrega
                                    print(f"📦 Mensaje de entrega obtenido desde BD para campaña {campania_cliente}")
                                    
                                    # 🔥 REGISTRAR LA VENTA
                                    cantidad = 1  # Por ahora asumimos cantidad 1
                                    precio_unitario = documento.precio if documento.precio else 0
                                    monto_total = cantidad * precio_unitario
                                    
                                    # 🔥 DEBUG: Ver qué valor tiene EstadoVenta.CONFIRMADA
                                    print(f"🔍 DEBUG - EstadoVenta.CONFIRMADA: {EstadoVenta.CONFIRMADA}")
                                    print(f"🔍 DEBUG - Tipo: {type(EstadoVenta.CONFIRMADA)}")
                                    print(f"🔍 DEBUG - Valor como string: {str(EstadoVenta.CONFIRMADA)}")

                                    # Y luego, para forzar el valor correcto, usá:
                                    estado_valor = "confirmada"  # Forzamos el string en minúsculas
                                    print(f"🔍 DEBUG - Valor forzado: {estado_valor}")

                                    nueva_venta = Venta(
                                        empresa_id=empresa.id,
                                        cliente_id=cliente_pendiente.id,
                                        campania_id=campania_cliente,
                                        producto_nombre=documento.nombre.replace('.pdf', ''),
                                        cantidad=cantidad,
                                        precio_unitario=precio_unitario,
                                        monto_total=monto_total,
                                        estado=estado_valor,
                                        comprobante_url=datos.get("ultimo_comprobante", {}).get("url"),
                                        notas=f"Venta aprobada el {datetime.datetime.now()}"
                                    )
                                    db.add(nueva_venta)
                                    db.commit()  # ← IMPORTANTE: commit antes de emitir
                                    db.refresh(nueva_venta)
                                    
                                    # 🔥 EMITIR EVENTO WEBSOCKET PARA ACTUALIZAR DASHBOARD EN TIEMPO REAL
                                    venta_dict = {
                                        "id": nueva_venta.id,
                                        "empresa_id": nueva_venta.empresa_id,
                                        "cliente_id": nueva_venta.cliente_id,
                                        "cliente_nombre": cliente_pendiente.nombre,
                                        "cliente_telefono": cliente_pendiente.telefono,
                                        "campania_id": nueva_venta.campania_id,
                                        "producto_nombre": nueva_venta.producto_nombre,
                                        "cantidad": nueva_venta.cantidad,
                                        "precio_unitario": nueva_venta.precio_unitario,
                                        "monto_total": nueva_venta.monto_total,
                                        "estado": nueva_venta.estado,
                                        "comprobante_url": nueva_venta.comprobante_url,
                                        "notas": nueva_venta.notas,
                                        "fecha_venta": nueva_venta.fecha_venta.isoformat() if nueva_venta.fecha_venta else None,
                                        "fecha_actualizacion": nueva_venta.fecha_actualizacion.isoformat() if nueva_venta.fecha_actualizacion else None
                                    }
                                    await emitir_nueva_venta(venta_dict, empresa.id)
                                    print(f"📡 Evento WebSocket emitido para venta ID: {nueva_venta.id}")
                                    
                                    print(f"💰 Venta registrada: {campania_cliente} - ${monto_total}")
                                    
                                else:
                                    print(f"⚠️ No se encontró mensaje de entrega para campaña {campania_cliente}, usando legacy")
                                    rag_temp = RAGService(db, empresa.id, cliente_pendiente.id, campania_cliente)
                                    mensaje_material = rag_temp.obtener_mensaje_entrega_legacy(campania_cliente)
                                
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_material)
                                
                            else:  # RECHAZAR
                                datos["ultimo_comprobante"]["estado_pago"] = "rechazado"
                                datos["ultimo_comprobante"]["fecha_rechazo"] = str(datetime.datetime.now())
                                mensaje_rechazo = "❌ Hubo un problema con tu comprobante. Por favor, contacta a un asesor para más detalles."
                                enviar_mensaje_whatsapp(cliente_pendiente.telefono, mensaje_rechazo)
                            
                            cliente_pendiente.datos_estructurados = datos
                            db.commit()
                            
                            return {"status": "ok", "message": f"Pago {accion} para cliente {cliente_id}"}
            
            return {"status": "ok", "message": "Formato no reconocido o cliente sin pago pendiente"}
        
        # Guardar/Actualizar cliente con campaña
        if not cliente:
            # Cliente nuevo
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
        
        # Verificar campaña antes de RAG
        campania_activa = None
        if cliente.datos_estructurados:
            campania_activa = cliente.datos_estructurados.get("campania_activa")
            print(f"🎯 CAMPAÑA ACTIVA PARA RAG: '{campania_activa}'")
            
            if not campania_activa:
                print("⚠️ Cliente sin campaña activa. Usando fallback.")
        else:
            print("⚠️ No hay datos_estructurados en cliente")
        
        # Inicializar servicios
        rag = RAGService(
            db=db, 
            empresa_id=empresa.id, 
            cliente_id=cliente.id,
            campania_id=campania_activa
        )
        memoria = MemoriaService(db, cliente.id)
        
        # Buscar documentos
        print(f"🔍 Buscando documentos para: '{texto_mensaje}' con campaña '{campania_activa}'")
        resumen_cliente = memoria.obtener_resumen()
        documentos_relevantes = rag.buscar_similares(texto_mensaje, top_k=3)
        
        print(f"📚 Documentos encontrados: {len(documentos_relevantes)}")
        for i, doc in enumerate(documentos_relevantes):
            print(f"  {i+1}. Documento: {doc.get('documento', 'N/A')} - Similitud: {doc.get('similitud', 0):.4f}")
            print(f"     Texto: {doc.get('texto', '')[:100]}...")
        
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