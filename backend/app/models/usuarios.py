from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=True)  # Ahora puede ser nulo (para usuarios sociales)
    google_id = Column(String(255), unique=True, nullable=True)  # ID de Google
    facebook_id = Column(String(255), unique=True, nullable=True)  # ID de Facebook
    foto_url = Column(String(500), nullable=True)  # URL de foto de perfil
    auth_provider = Column(String(50), nullable=False, default='local')  # local, google, facebook
    rol = Column(String(50), nullable=False, default="dueño")
    activo = Column(Boolean, default=True)
    ultimo_acceso = Column(DateTime(timezone=True), nullable=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    empresa = relationship("Empresa", backref="usuarios")

    def __repr__(self):
        return f"<Usuario {self.email} - Empresa {self.empresa_id}>"