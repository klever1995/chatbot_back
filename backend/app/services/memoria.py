from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.conversacion import Conversacion
import json

class MemoriaService:
    def __init__(self, db: Session, cliente_id: int):
        self.db = db
        self.cliente_id = cliente_id
        self.cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    
    def obtener_resumen(self) -> str:
        """Obtiene el resumen actual del cliente"""
        if self.cliente and self.cliente.resumen:
            return self.cliente.resumen
        return "Cliente sin historial previo"
    
    def obtener_datos_estructurados(self) -> dict:
        """Obtiene los datos estructurados del cliente"""
        if self.cliente and self.cliente.datos_estructurados:
            return self.cliente.datos_estructurados
        return {}
    
    def actualizar_resumen(self, pregunta: str, respuesta: str):
        """
        Actualiza el resumen del cliente basado en la interacción
        Por ahora es simple, después se puede mejorar con LLM
        """
        if not self.cliente:
            return
        
        # Versión simple: concatenar últimas interacciones
        nuevo_resumen = f"Última interacción - P: {pregunta[:50]}... R: {respuesta[:50]}..."
        
        # Actualizar cliente
        self.cliente.resumen = nuevo_resumen
        self.cliente.ultima_interaccion = None  
        self.db.commit()
    
    def guardar_dato_estructurado(self, clave: str, valor):
        """Guarda un dato estructurado en el campo JSON"""
        if not self.cliente:
            return
        
        datos = self.cliente.datos_estructurados or {}
        datos[clave] = valor
        
        self.cliente.datos_estructurados = datos
        self.db.commit()