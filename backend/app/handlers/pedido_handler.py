import datetime
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.pedido import Pedido, EstadoPedido
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.whatsapp_sender import enviar_mensaje_whatsapp, enviar_mensaje_con_botones
from app.socket_manager import emitir_nuevo_pedido, emitir_pedido_actualizado  # 🔥 NUEVO

async def responder_pregunta_restaurante(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    texto_mensaje: str,
    campania_id: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Responde preguntas del restaurante usando RAG (menú, horarios, direcciones, etc.)
    """
    # Inicializar RAG y Memoria
    rag = RAGService(
        db=db,
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        campania_id=campania_id
    )
    memoria = MemoriaService(db, cliente.id)
    
    # Buscar documentos relevantes del menú
    print(f"🔍 Buscando en campaña '{campania_id}' para: '{texto_mensaje}'")
    resumen_cliente = memoria.obtener_resumen()
    documentos_relevantes = rag.buscar_similares(texto_mensaje, top_k=3)
    
    print(f"📚 Documentos encontrados: {len(documentos_relevantes)}")
    for i, doc in enumerate(documentos_relevantes):
        print(f"  {i+1}. Documento: {doc.get('documento', 'N/A')} - Similitud: {doc.get('similitud', 0):.4f}")
    
    contexto = "\n\n".join([doc["texto"] for doc in documentos_relevantes])
    
    # Generar respuesta con LLM
    respuesta_texto = rag.generar_respuesta_llm(
        consulta=texto_mensaje,
        contexto=contexto,
        resumen_cliente=resumen_cliente
    )
    
    # Guardar respuesta del bot en conversación
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
    
    # Actualizar memoria con la conversación
    memoria.actualizar_resumen(texto_mensaje, respuesta_texto)
    
    return respuesta_texto

async def procesar_comprobante_pedido(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    comprobante_url: str,
    imagen_info: dict,
    texto_pedido: str,
    monto_total: float,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa el comprobante de un pedido y guarda el pedido en la base de datos
    """
    # Crear el pedido en la base de datos
    nuevo_pedido = Pedido(
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        campania_id=cliente.datos_estructurados.get("campania_activa") if cliente.datos_estructurados else None,
        texto_pedido=texto_pedido,
        monto_total=monto_total,
        comprobante_url=comprobante_url,
        estado=EstadoPedido.PENDIENTE
    )
    db.add(nuevo_pedido)
    db.commit()
    db.refresh(nuevo_pedido)
    
    # Guardar referencia del pedido en datos_estructurados del cliente
    if not cliente.datos_estructurados:
        cliente.datos_estructurados = {}
    cliente.datos_estructurados["ultimo_pedido_id"] = nuevo_pedido.id
    db.commit()
    
    # 🔥 Construir diccionario del pedido para WebSocket
    pedido_dict = {
        "id": nuevo_pedido.id,
        "empresa_id": nuevo_pedido.empresa_id,
        "cliente_id": nuevo_pedido.cliente_id,
        "cliente_nombre": cliente.nombre or "",
        "cliente_telefono": cliente.telefono,
        "campania_id": nuevo_pedido.campania_id,
        "texto_pedido": nuevo_pedido.texto_pedido,
        "monto_total": nuevo_pedido.monto_total,
        "comprobante_url": nuevo_pedido.comprobante_url,
        "estado": nuevo_pedido.estado,
        "notas": nuevo_pedido.notas,
        "fecha_creacion": nuevo_pedido.fecha_creacion.isoformat() if nuevo_pedido.fecha_creacion else None,
        "fecha_confirmacion": nuevo_pedido.fecha_confirmacion.isoformat() if nuevo_pedido.fecha_confirmacion else None
    }
    
    # 🔥 Emitir evento de nuevo pedido vía WebSocket
    await emitir_nuevo_pedido(pedido_dict, empresa.id)
    print(f"📡 Evento WebSocket emitido para nuevo pedido ID: {nuevo_pedido.id}")
    
    # Enviar notificación al dueño con el resumen del pedido y botones
    texto_cabecera = (
        f"🔔 *NUEVO PEDIDO CON COMPROBANTE*\n\n"
        f"*Cliente:* {cliente.nombre or 'Desconocido'}\n"
        f"*Teléfono:* {cliente.telefono}\n"
        f"*Pedido:* {texto_pedido}\n"
        f"*Total:* ${monto_total:.2f}\n"
        f"*Comprobante:* {comprobante_url}"
    )
    
    await enviar_mensaje_con_botones(
        telefono_destino=empresa.telefono_dueño,
        texto_cabecera=texto_cabecera,
        cliente_id=cliente.id,
        token=whatsapp_token,
        phone_number_id=phone_number_id
    )
    
    # Responder al cliente que su pedido está en revisión
    mensaje_cliente = f"✅ ¡Gracias por enviar tu comprobante! Hemos registrado tu pedido por ${monto_total:.2f}. El dueño lo revisará y te confirmará en breve."
    await enviar_mensaje_whatsapp(
        telefono_destino=cliente.telefono,
        mensaje=mensaje_cliente,
        token=whatsapp_token,
        phone_number_id=phone_number_id
    )
    
    return nuevo_pedido

async def aprobar_pedido(
    db: Session,
    empresa: Empresa,
    cliente_pendiente: Cliente,
    accion: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Procesa la aprobación o rechazo del dueño para un pedido
    """
    # Obtener el pedido pendiente más reciente del cliente
    pedido = db.query(Pedido).filter(
        Pedido.cliente_id == cliente_pendiente.id,
        Pedido.empresa_id == empresa.id,
        Pedido.estado == EstadoPedido.PENDIENTE
    ).order_by(Pedido.fecha_creacion.desc()).first()
    
    if not pedido:
        print(f"⚠️ No se encontró pedido pendiente para cliente {cliente_pendiente.id}")
        return False
    
    if accion == "APROBAR":
        # Actualizar estado del pedido
        pedido.estado = EstadoPedido.CONFIRMADO
        pedido.fecha_confirmacion = datetime.datetime.now()
        db.commit()
        
        # Enviar mensaje de confirmación al cliente
        mensaje_confirmacion = f"✅ ¡Pedido confirmado! Tu pedido ha sido aprobado. En breve lo estaremos preparando.\n\n📋 *Resumen:* {pedido.texto_pedido}\n💰 *Total pagado:* ${pedido.monto_total:.2f}"
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_confirmacion,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
        
    else:  # RECHAZAR
        # Actualizar estado del pedido
        pedido.estado = EstadoPedido.RECHAZADO
        db.commit()
        
        # Enviar mensaje de rechazo al cliente
        mensaje_rechazo = f"❌ Hubo un problema con tu comprobante o con tu pedido. Por favor, contacta al restaurante directamente para más detalles.\n\n📋 *Pedido:* {pedido.texto_pedido}\n💰 *Total:* ${pedido.monto_total:.2f}"
        await enviar_mensaje_whatsapp(
            telefono_destino=cliente_pendiente.telefono,
            mensaje=mensaje_rechazo,
            token=whatsapp_token,
            phone_number_id=phone_number_id
        )
    
    # 🔥 Construir diccionario del pedido actualizado para WebSocket
    pedido_dict = {
        "id": pedido.id,
        "empresa_id": pedido.empresa_id,
        "cliente_id": pedido.cliente_id,
        "cliente_nombre": cliente_pendiente.nombre or "",
        "cliente_telefono": cliente_pendiente.telefono,
        "campania_id": pedido.campania_id,
        "texto_pedido": pedido.texto_pedido,
        "monto_total": pedido.monto_total,
        "comprobante_url": pedido.comprobante_url,
        "estado": pedido.estado,
        "notas": pedido.notas,
        "fecha_creacion": pedido.fecha_creacion.isoformat() if pedido.fecha_creacion else None,
        "fecha_confirmacion": pedido.fecha_confirmacion.isoformat() if pedido.fecha_confirmacion else None
    }
    
    # 🔥 Emitir evento de pedido actualizado vía WebSocket
    await emitir_pedido_actualizado(pedido_dict, empresa.id)
    print(f"📡 Evento WebSocket emitido para pedido ID: {pedido.id} - {accion}")
    
    return True