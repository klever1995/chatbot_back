from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import engine, Base
from app.api.v1.endpoints import empresas, documentos, whatsapp, ventas, usuarios, auth  
from app.models import empresa, cliente, conversacion, documento 
from app.socket_manager import socket_app  # 🔥 IMPORTAR

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chatbot Sublimados API")

# ✅ CORS CORRECTO
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   
        "http://localhost:5173",  
        "https://b6eb-201-183-99-16.ngrok-free.app"  
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔥 MONTAR SOCKET
app.mount("/socket.io", socket_app)

# Routers
app.include_router(empresas.router, prefix="/api/v1")
app.include_router(documentos.router, prefix="/api/v1") 
app.include_router(whatsapp.router, prefix="/api/v1")
app.include_router(ventas.router, prefix="/api/v1")
app.include_router(usuarios.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "API funcionando correctamente"}

@app.get("/health")
def health_check():
    return {"status": "ok"}