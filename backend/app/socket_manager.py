# app/socket_manager.py
import socketio
import logging

logger = logging.getLogger(__name__)

# Crear servidor Socket.IO
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:5173', 'http://localhost:3000'],
    logger=True,
    engineio_logger=True
)

@sio.event
async def connect(sid, environ):
    logger.info(f"Cliente conectado: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Cliente desconectado: {sid}")