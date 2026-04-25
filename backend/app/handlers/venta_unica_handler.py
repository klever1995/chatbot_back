import datetime
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.documento import Documento
from app.models.ventas import Venta, EstadoVenta
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones
from app.socket_manager import emitir_nueva_venta

async def procesar_mensaje_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    texto_mensaje: str,
    imagen_info: dict,
    audio_url: str,
    campania_activa: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa un mensaje normal de venta única (respuesta RAG)
    """
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
    await enviar_mensaje_whatsapp(
        telefono_destino=cliente.telefono,
        mensaje=respuesta_texto,
        token=whatsapp_token,
        phone_number_id=phone_number_id
    )
    
    # Actualizar memoria
    memoria.actualizar_resumen(texto_mensaje, respuesta_texto)
    
    return respuesta_texto

async def procesar_comprobante_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    url_comprobante: str,
    imagen_info: dict,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa un comprobante de pago para venta única
    """
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
        await enviar_mensaje_con_botones(
            telefono_destino=empresa.telefono_dueño,
            texto_cabecera=texto_cabecera,
            cliente_id=cliente.id,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
    
    return True

async def aprobar_venta_unica(
    db: Session,
    empresa: Empresa,
    cliente_pendiente: Cliente,
    accion: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa la aprobación o rechazo del dueño para venta única
    """
    datos = cliente_pendiente.datos_estructurados
    campania_cliente = datos.get("campania_activa")
    
    if accion == "APROBAR":
        datos["ultimo_comprobante"]["estado_pago"] = "confirmado"
        datos["ultimo_comprobante"]["fecha_confirmacion"] = str(datetime.datetime.now())
        
        mensaje_confirmacion = "✅ ¡Buenas noticias! Tu pago ha sido verificado y ya tienes acceso al curso. 😊"
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_confirmacion,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
        
        print(f"📦 Buscando mensaje de entrega para campaña: {campania_cliente}")
        
        documento = db.query(Documento).filter(
            Documento.empresa_id == empresa.id,
            Documento.campania_id == campania_cliente
        ).first()
        
        if documento and documento.mensaje_entrega:
            mensaje_material = documento.mensaje_entrega
            print(f"📦 Mensaje de entrega obtenido desde BD para campaña {campania_cliente}")
            
            cantidad = 1
            precio_unitario = documento.precio if documento.precio else 0
            monto_total = cantidad * precio_unitario
            estado_valor = "confirmada"

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
            db.commit()
            db.refresh(nueva_venta)
            
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
        
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_material,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
        
    else:  # RECHAZAR
        datos["ultimo_comprobante"]["estado_pago"] = "rechazado"
        datos["ultimo_comprobante"]["fecha_rechazo"] = str(datetime.datetime.now())
        mensaje_rechazo = "❌ Hubo un problema con tu comprobante. Por favor, contacta a un asesor para más detalles."
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_rechazo,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
    
    cliente_pendiente.datos_estructurados = datos
    db.commit()
    
    return True