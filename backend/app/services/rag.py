import os
from typing import List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
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
    def __init__(self, db: Session, empresa_id: int, cliente_id: int = None):
        self.db = db
        self.empresa_id = empresa_id
        self.cliente_id = cliente_id
    
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
        
        system_prompt = f"""Eres un asistente virtual de una tienda de sublimados.
        Usa la siguiente información de la empresa para responder:
        
        {contexto}
        
        Historial del cliente (resumen): {resumen_cliente}
        
        Historial de la conversación actual:
        {historial}
        
        IMPORTANTE: Mantén la coherencia con la conversación. No repitas saludos ni información que ya hayas proporcionado antes.
        Sé amable, profesional y responde SOLO con información que esté en el contexto.
        Si no sabes algo, sugiere contactar a un asesor humano."""
        
        respuesta = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": consulta}
            ],
            temperature=0.7
        )
        
        return respuesta.choices[0].message.content
    
    def guardar_documento(self, nombre_archivo: str, contenido_bytes: bytes):
        """Procesa y guarda un documento en la base de datos vectorial"""
        from app.models.documento import Documento, ChunkDocumento
        
        # Extraer texto
        texto = self.extraer_texto_pdf(contenido_bytes)
        
        # Crear registro del documento
        doc = Documento(
            empresa_id=self.empresa_id,
            nombre=nombre_archivo,
            hash_contenido=hashlib.md5(contenido_bytes).hexdigest()
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
        """Busca chunks similares a la consulta usando similitud de coseno"""
        from app.models.documento import ChunkDocumento
        
        # Generar embedding de la consulta
        embedding_consulta = self.generar_embedding(consulta)
        
        # Buscar chunks de la empresa
        chunks = self.db.query(ChunkDocumento).filter(
            ChunkDocumento.documento.has(empresa_id=self.empresa_id)
        ).all()
        
        # Calcular similitud de coseno
        resultados = []
        for chunk in chunks:
            similitud = np.dot(embedding_consulta, chunk.embedding) / (
                np.linalg.norm(embedding_consulta) * np.linalg.norm(chunk.embedding)
            )
            resultados.append({
                "texto": chunk.texto,
                "similitud": similitud,
                "documento": chunk.documento.nombre
            })
        
        # Ordenar por similitud y devolver top_k
        resultados.sort(key=lambda x: x["similitud"], reverse=True)
        return resultados[:top_k]