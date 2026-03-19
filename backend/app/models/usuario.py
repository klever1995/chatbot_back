from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    nombre          = Column(String(150), nullable=False)
    foto_url        = Column(String(500), nullable=True)
    google_id       = Column(String(100), unique=True, nullable=True)
    activo          = Column(Boolean, default=True)
    fecha_registro  = Column(DateTime(timezone=True), server_default=func.now())
    fecha_ultimo_login = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Usuario {self.email}>"
