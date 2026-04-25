import os
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from openai import OpenAI
from PyPDF2 import PdfReader
from io import BytesIO
import hashlib
from app.models.empresa import Empresa

class RAGService:
    def __init__(self, db: Session, empresa_id: int, cliente_id: int = None, campania_id: Optional[str] = None):
        self.db = db
        self.empresa_id = empresa_id
        self.cliente_id = cliente_id
        self.campania_id = campania_id
        
        # 🔥 OBTENER LA EMPRESA DE LA BASE DE DATOS PARA SUS CREDENCIALES
        self.empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not self.empresa:
            raise ValueError(f"Empresa con ID {empresa_id} no encontrada")
        
        # 🔥 INICIALIZAR CLIENTE DE OPENAI CON LA API KEY DE LA EMPRESA
        self.client = OpenAI(
            api_key=self.empresa.openai_api_key,
            base_url=self.empresa.openai_api_base if self.empresa.openai_api_base else None
        )
        
        # 🔥 MODELOS CONFIGURABLES POR EMPRESA
        self.embedding_model = self.empresa.openai_embedding_model or "text-embedding-ada-002"
        self.chat_model = self.empresa.openai_chat_model or "gpt-4o"
    
    def obtener_historial_reciente(self, limite: int = 5) -> str:
        """Obtiene los últimos mensajes de la conversación actual"""
        if not self.cliente_id:
            return ""
        
        from app.models.conversacion import Conversacion, TipoEmisor
        
        mensajes = self.db.query(Conversacion).filter(
            Conversacion.cliente_id == self.cliente_id
        ).order_by(Conversacion.timestamp.desc()).limit(limite).all()
        
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
        """Genera embedding usando el modelo configurado de OpenAI"""
        respuesta = self.client.embeddings.create(
            model=self.embedding_model,
            input=texto
        )
        return respuesta.data[0].embedding
    
    def generar_respuesta_llm(self, consulta: str, contexto: str, resumen_cliente: str = "") -> str:
        """Genera respuesta usando el modelo configurado de OpenAI con historial de conversación"""
        
        historial = self.obtener_historial_reciente()
        
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
        
        respuesta = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": consulta}
            ],
            temperature=0.4
        )
        
        return respuesta.choices[0].message.content
    
    def guardar_documento(self, nombre_archivo: str, contenido_bytes: bytes, campania_id: Optional[str] = None, mensaje_entrega: Optional[str] = None, precio: Optional[float] = None, tipo_campania: Optional[str] = "producto_unico"):
        """Procesa y guarda un documento en la base de datos vectorial"""
        from app.models.documento import Documento, ChunkDocumento
        import re
        import random
        import string
        
        # GENERAR IDENTIFICADOR AUTOMÁTICO SI NO VIENE
        if not campania_id or not campania_id.strip():
            nombre_base = os.path.splitext(nombre_archivo)[0]
            nombre_normalizado = nombre_base.lower().strip()
            nombre_normalizado = re.sub(r'[^a-z0-9_]', '_', nombre_normalizado)
            nombre_normalizado = re.sub(r'_+', '_', nombre_normalizado).strip('_')
            
            codigo_corto = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            
            if nombre_normalizado:
                campania_id = f"{nombre_normalizado}_{codigo_corto}"
            else:
                campania_id = f"campania_{codigo_corto}"
            print(f"🔑 Campaña generada automáticamente en RAG: {campania_id}")
        
        # Validar tipo_campania
        if tipo_campania not in ["producto_unico", "pedido_multiple", "informativo"]:
            tipo_campania = "producto_unico"
        
        # Extraer texto
        texto = self.extraer_texto_pdf(contenido_bytes)
        
        # Crear registro del documento
        doc = Documento(
            empresa_id=self.empresa_id,
            nombre=nombre_archivo,
            hash_contenido=hashlib.md5(contenido_bytes).hexdigest(),
            campania_id=campania_id,
            mensaje_entrega=mensaje_entrega,
            precio=precio,
            tipo_campania=tipo_campania  # 🔥 NUEVO CAMPO
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
        """Busca chunks similares usando pgvector con filtro por campaña"""
        from app.models.documento import ChunkDocumento, Documento
        
        embedding_consulta = self.generar_embedding(consulta)
        
        query = self.db.query(
            ChunkDocumento,
            Documento.nombre.label("documento_nombre")
        ).join(
            Documento, ChunkDocumento.documento_id == Documento.id
        ).filter(
            Documento.empresa_id == self.empresa_id
        )
        
        if self.campania_id:
            query = query.filter(Documento.campania_id == self.campania_id)
            print(f"🔍 Buscando en campaña: {self.campania_id}")
        else:
            print("⚠️ Buscando en TODOS los documentos (sin filtro de campaña)")
        
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
        
        resultados.sort(key=lambda x: x["similitud"], reverse=True)
        return resultados[:top_k]