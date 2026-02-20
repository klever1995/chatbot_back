from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import engine, Base
from app.api.v1.endpoints import empresas, documentos, whatsapp 
from app.models import empresa, cliente, conversacion, documento 

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chatbot Sublimados API")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos los headers
)

# Incluir routers
app.include_router(empresas.router, prefix="/api/v1")
app.include_router(documentos.router, prefix="/api/v1") 
app.include_router(whatsapp.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "API funcionando correctamente"}

@app.get("/health")
def health_check():
    return {"status": "ok"}