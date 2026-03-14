import os
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from openai import AzureOpenAI
from PyPDF2 import PdfReader
from io import BytesIO
import hashlib

# Inicializar cliente de Azure OpenAI
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
)

AZURE_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

class RAGService:
    def __init__(self, db: Session, empresa_id: int, cliente_id: int = None, campania_id: Optional[str] = None):
        self.db = db
        self.empresa_id = empresa_id
        self.cliente_id = cliente_id
        self.campania_id = campania_id  # 🔥 NUEVO: ID de la campaña activa
    
    def obtener_historial_reciente(self, limite: int = 5) -> str:
        """Obtiene los últimos mensajes de la conversación actual"""
        if not self.cliente_id:
            return ""
        
        from app.models.conversacion import Conversacion, TipoEmisor
        
        mensajes = self.db.query(Conversacion).filter(
            Conversacion.cliente_id == self.cliente_id
        ).order_by(Conversacion.timestamp.desc()).limit(limite).all()
        
        # Invertir para orden cronológico
        mensajes.reverse()
        
        historial = []
        for msg in mensajes:
            emisor = "Cliente" if msg.emisor == TipoEmisor.CLIENTE else "Bot"
            historial.append(f"{emisor}: {msg.mensaje}")
        
        return "\n".join(historial)
    
    def extraer_texto_pdf(self, archivo_bytes: bytes) -> str:
        """Extrae texto de un archivo PDF"""
        texto = ""
        pdf = PdfReader(BytesIO(archivo_bytes))
        for pagina in pdf.pages:
            texto += pagina.extract_text()
        return texto
    
    def dividir_en_chunks(self, texto: str, tamano_chunk: int = 500, solapamiento: int = 50) -> List[str]:
        """Divide el texto en fragmentos más pequeños para embedding"""
        palabras = texto.split()
        chunks = []
        
        for i in range(0, len(palabras), tamano_chunk - solapamiento):
            chunk = " ".join(palabras[i:i + tamano_chunk])
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def generar_embedding(self, texto: str) -> List[float]:
        """Genera embedding usando Azure OpenAI"""
        respuesta = client.embeddings.create(
            model=AZURE_EMBEDDING_DEPLOYMENT,
            input=texto
        )
        return respuesta.data[0].embedding
    
    def generar_respuesta_llm(self, consulta: str, contexto: str, resumen_cliente: str = "") -> str:
        """Genera respuesta usando GPT-4o de Azure con historial de conversación"""
        
        # Obtener historial reciente
        historial = self.obtener_historial_reciente()
        
        # 🔥 MODIFICADO: Incluir información de la campaña activa en el prompt
        info_campania = f"Estás vendiendo el curso de {self.campania_id}." if self.campania_id else ""
        
        system_prompt = f"""Eres una persona normal que vende cursos por WhatsApp, no un asistente virtual ni un bot. 
        Habla como lo haría cualquier vendedor en una conversación real de WhatsApp: natural, directo y sin rodeos.
        
        {info_campania}
        
        Información del curso (SOLO de la campaña actual):
        {contexto}
        
        Historial del cliente (resumen): {resumen_cliente}
        
        Historial de la conversación actual:
        {historial}
        
        IMPORTANTE: Mantén la coherencia con la conversación. No repitas saludos ni información que ya hayas proporcionado antes.
        Sé amable, profesional y responde SOLO con información que esté en el contexto.
        Si no sabes algo, sugiere contactar a un asesor humano.
        Respondé como una persona normal en WhatsApp, sin usar asteriscos, guiones ni ningún símbolo raro. Texto plano siempre."""
        
        respuesta = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": consulta}
            ],
            temperature=0.4
        )
        
        return respuesta.choices[0].message.content
    
    def guardar_documento(self, nombre_archivo: str, contenido_bytes: bytes, campania_id: Optional[str] = None):
        """Procesa y guarda un documento en la base de datos vectorial"""
        from app.models.documento import Documento, ChunkDocumento
        
        # Extraer texto
        texto = self.extraer_texto_pdf(contenido_bytes)
        
        # Crear registro del documento (ahora guardamos también la campaña)
        doc = Documento(
            empresa_id=self.empresa_id,
            nombre=nombre_archivo,
            hash_contenido=hashlib.md5(contenido_bytes).hexdigest(),
            campania_id=campania_id  # 🔥 NUEVO: Asociar documento a una campaña
        )
        self.db.add(doc)
        self.db.flush()
        
        # Dividir en chunks y generar embeddings
        chunks = self.dividir_en_chunks(texto)
        for i, chunk_texto in enumerate(chunks):
            embedding = self.generar_embedding(chunk_texto)
            
            chunk = ChunkDocumento(
                documento_id=doc.id,
                indice=i,
                texto=chunk_texto,
                embedding=embedding
            )
            self.db.add(chunk)
        
        self.db.commit()
        return doc
    
    def buscar_similares(self, consulta: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """🔥 VERSIÓN OPTIMIZADA: Busca chunks similares usando pgvector con filtro por campaña"""
        from app.models.documento import ChunkDocumento, Documento
        
        # Generar embedding de la consulta
        embedding_consulta = self.generar_embedding(consulta)
        
        # Construir consulta base con filtros
        query = self.db.query(
            ChunkDocumento,
            Documento.nombre.label("documento_nombre")
        ).join(
            Documento, ChunkDocumento.documento_id == Documento.id
        ).filter(
            Documento.empresa_id == self.empresa_id
        )
        
        # 🔥 FILTRO CRÍTICO: Solo buscar en documentos de la campaña activa
        if self.campania_id:
            query = query.filter(Documento.campania_id == self.campania_id)
            print(f"🔍 Buscando en campaña: {self.campania_id}")
        else:
            print("⚠️ Buscando en TODOS los documentos (sin filtro de campaña)")
        
        # Ejecutar consulta y calcular similitud (versión mejorada con ORDER BY de pgvector)
        # Nota: Idealmente usarías la función de distancia de pgvector directamente,
        # pero como estamos en SQLAlchemy, calculamos en Python por ahora
        chunks = query.all()
        
        resultados = []
        for chunk, doc_nombre in chunks:
            similitud = np.dot(embedding_consulta, chunk.embedding) / (
                np.linalg.norm(embedding_consulta) * np.linalg.norm(chunk.embedding)
            )
            resultados.append({
                "texto": chunk.texto,
                "similitud": similitud,
                "documento": doc_nombre,
                "documento_id": chunk.documento_id,
                "chunk_id": chunk.id
            })
        
        # Ordenar por similitud y devolver top_k
        resultados.sort(key=lambda x: x["similitud"], reverse=True)
        return resultados[:top_k]
    
    # 🔥 NUEVO MÉTODO: Obtener mensaje de entrega del producto desde el PDF de la campaña
    def obtener_mensaje_entrega(self) -> Optional[str]:
        """
        Busca en el documento de la campaña activa la sección de entrega del producto
        y devuelve el mensaje listo para enviar al cliente
        """
        if not self.campania_id:
            print("❌ No hay campaña activa para obtener mensaje de entrega")
            return None
        
        from app.models.documento import Documento, ChunkDocumento
        
        # Buscar chunks que contengan "ENTREGA_PRODUCTO" o "mensaje de entrega" en el texto
        # Asumimos que en el PDF hay una sección claramente identificada
        query = self.db.query(ChunkDocumento).join(
            Documento, ChunkDocumento.documento_id == Documento.id
        ).filter(
            Documento.empresa_id == self.empresa_id,
            Documento.campania_id == self.campania_id
        ).filter(
            # Buscar patrones que indiquen la sección de entrega
            (ChunkDocumento.texto.ilike("%entrega%producto%")) |
            (ChunkDocumento.texto.ilike("%mensaje%entrega%")) |
            (ChunkDocumento.texto.ilike("%SECCION:%ENTREGA%")) |
            (ChunkDocumento.texto.ilike("%material%acceso%"))
        ).order_by(ChunkDocumento.indice).limit(3).all()
        
        if not query:
            print(f"⚠️ No se encontró sección de entrega para campaña {self.campania_id}")
            # Fallback: devolver un mensaje genérico
            return "✅ ¡Gracias por tu compra! En breve recibirás el acceso al material."
        
        # Combinar los chunks encontrados para formar el mensaje completo
        mensaje_completo = "\n\n".join([chunk.texto for chunk in query])
        
        # Limpiar el mensaje (quitar posibles marcadores como "SECCION: ENTREGA_PRODUCTO")
        import re
        mensaje_limpio = re.sub(r"SECCION:\s*[A-Z_]+", "", mensaje_completo, flags=re.IGNORECASE)
        mensaje_limpio = mensaje_limpio.strip()
        
        print(f"📦 Mensaje de entrega obtenido para campaña {self.campania_id}")
        return mensaje_limpio
    
    # 🔥 MÉTODO DE RESPALDO: Para mantener compatibilidad con código existente
    def obtener_mensaje_entrega_legacy(self, campania: str) -> str:
        """
        Versión legacy que devuelve mensajes predefinidos por campaña
        Útil mientras se migran los PDFs a tener la sección de entrega
        """
        mensajes = {
            "lettering": (
                "✅ ¡Gracias por tu paciencia! Tu material de LETTERING ya está listo. Aquí tienes el acceso para descargarlo:\n\n"
                "[Acceso al Pack de Lettering](https://drive.google.com/drive/folders/1o1281qJnphKE3ClYHSHw1vNg6U?usp=shar)\n\n"
                "Incluye:\n"
                "- Guías y libros digitales\n"
                "- Plantillas de práctica\n"
                "- Cuadernillo de caligrafía\n"
                "- Técnicas y secretos para mejorar tus diseños\n\n"
                "Todo es digital (PDF) y tendrás acceso de por vida. Si necesitas ayuda con algo o tienes dudas, no dudes en escribirme. ¡Gracias por tu compra y disfruta de tu aventura creativa! 😊"
            ),
            "reposteria": (
                "✅ ¡Gracias por tu compra! Aquí tienes acceso al curso de REPOSTERÍA:\n\n"
                "[Acceso al Curso de Repostería](https://drive.google.com/drive/folders/tu-enlace-reposteria)\n\n"
                "Incluye recetarios, videos y guías paso a paso. ¡Disfruta!"
            )
        }
        return mensajes.get(campania, mensajes["lettering"])