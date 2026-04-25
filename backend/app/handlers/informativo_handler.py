from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.conversacion import Conversacion, TipoEmisor
from app.services.rag import RAGService
from app.services.memoria import MemoriaService
from app.services.whatsapp_sender import enviar_mensaje_whatsapp

async def responder_pregunta_informativo(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    texto_mensaje: str,
    campania_id: str,
    whatsapp_token: str,
    phone_number_id: str
):
    """
    Responde preguntas usando RAG para documentos informativos (no guarda ventas ni pedidos)
    """
    # Inicializar RAG y Memoria
    rag = RAGService(
        db=db,
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        campania_id=campania_id
    )
    memoria = MemoriaService(db, cliente.id)
    
    # Buscar documentos relevantes
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