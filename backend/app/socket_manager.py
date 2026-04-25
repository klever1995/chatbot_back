import socketio
from typing import Dict, Any

# Crear el servidor Socket.IO con CORS permitido para el frontend
sio = socketio.AsyncServer(
    cors_allowed_origins=[
        "*"      # Reemplazar con tu dominio en producción
    ],
    async_mode="asgi"
)

# Crear la aplicación ASGI para montar en FastAPI
socket_app = socketio.ASGIApp(sio)

@sio.event
async def connect(sid: str, environ: Dict[str, Any]):
    """
    Evento cuando un cliente se conecta
    """
    print(f"🔌 Cliente conectado: {sid}")
    await sio.emit("conexion_exitosa", {"message": "Conectado al servidor de eventos"}, room=sid)


@sio.event
async def disconnect(sid: str):
    """
    Evento cuando un cliente se desconecta
    """
    print(f"🔌 Cliente desconectado: {sid}")


@sio.event
async def join_empresa(sid: str, empresa_id: int):
    """
    Cliente se une a una sala específica para recibir eventos de su empresa
    """
    room_name = f"empresa_{empresa_id}"
    await sio.enter_room(sid, room_name)
    print(f"📌 Cliente {sid} se unió a sala: {room_name}")
    await sio.emit("joined", {"room": room_name}, room=sid)


@sio.event
async def leave_empresa(sid: str, empresa_id: int):
    """
    Cliente sale de una sala
    """
    room_name = f"empresa_{empresa_id}"
    await sio.leave_room(sid, room_name)
    print(f"📌 Cliente {sid} salió de sala: {room_name}")


# ==============================================
# FUNCIONES PARA VENTAS (producto único)
# ==============================================
async def emitir_nueva_venta(venta_dict: Dict[str, Any], empresa_id: int):
    """
    Emite un evento 'nueva_venta' a todos los clientes conectados
    que estén en la sala de la empresa correspondiente
    """
    room_name = f"empresa_{empresa_id}"
    print(f"📢 Emitiendo nueva venta a sala: {room_name}")
    await sio.emit("nueva_venta", venta_dict, room=room_name)


# ==============================================
# FUNCIONES PARA PEDIDOS (pedido múltiple)
# ==============================================
async def emitir_nuevo_pedido(pedido_dict: Dict[str, Any], empresa_id: int):
    """
    Emite un evento 'nuevo_pedido' a todos los clientes conectados
    que estén en la sala de la empresa correspondiente
    """
    room_name = f"empresa_{empresa_id}"
    print(f"📢 Emitiendo nuevo pedido a sala: {room_name}")
    await sio.emit("nuevo_pedido", pedido_dict, room=room_name)


async def emitir_pedido_actualizado(pedido_dict: Dict[str, Any], empresa_id: int):
    """
    Emite un evento 'pedido_actualizado' a todos los clientes conectados
    que estén en la sala de la empresa correspondiente
    """
    room_name = f"empresa_{empresa_id}"
    print(f"📢 Emitiendo pedido actualizado a sala: {room_name}")
    await sio.emit("pedido_actualizado", pedido_dict, room=room_name)