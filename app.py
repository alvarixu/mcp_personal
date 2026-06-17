import asyncio
from pathlib import Path

# Importaciones del SDK de MCP
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

# Importaciones de Starlette (Framework web asíncrono)
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

# ── MCP Server ────────────────────────────────────────────────────────────────
# Inicializamos el servidor MCP con un identificador único
mcp_app = Server("mcp-filesystem-azure")

# Obtenemos el directorio base donde se encuentra este script
BASE_DIR = Path(__file__).parent.resolve()


def ruta_segura(ruta: str) -> Path:
    """
    Función de seguridad: Resuelve una ruta relativa y asegura que esté
    dentro del directorio base permitido (BASE_DIR).
    Evita ataques de path traversal (ej. "../../../etc/passwd").
    """
    path = (BASE_DIR / ruta).resolve()
    # Si la ruta resuelta no comienza con el directorio base, es un acceso ilegal
    if not str(path).startswith(str(BASE_DIR)):
        raise PermissionError(f"Acceso denegado: '{ruta}' fuera del directorio permitido.")
    return path


# Decorador para registrar las herramientas disponibles en este servidor MCP
@mcp_app.list_tools()
async def listar_herramientas() -> list[Tool]:
    """
    Devuelve la lista de herramientas (Tools) que el servidor ofrece al cliente.
    Cada herramienta define un nombre, una descripción y un esquema JSON (inputSchema)
    que indica qué parámetros espera recibir.
    """
    return [
        Tool(
            name="listar_directorio",
            description="Lista el contenido de un directorio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {"type": "string", "default": "."}
                },
                "required": []
            }
        ),
        Tool(
            name="leer_archivo",
            description="Lee y devuelve el contenido de un archivo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {"type": "string"}
                },
                "required": ["ruta"]
            }
        ),
        Tool(
            name="escribir_archivo",
            description="Crea o sobreescribe un archivo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {"type": "string"},
                    "contenido": {"type": "string"}
                },
                "required": ["ruta", "contenido"]
            }
        ),
        Tool(
            name="info_archivo",
            description="Devuelve metadatos de un archivo o directorio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {"type": "string"}
                },
                "required": ["ruta"]
            }
        ),
    ]


# Decorador para manejar la ejecución de las herramientas registradas
@mcp_app.call_tool()
async def ejecutar_herramienta(nombre: str, arguments: dict) -> list[TextContent]:
    """
    Recibe el nombre de la herramienta a ejecutar y sus argumentos.
    Enruta la petición a la función correspondiente y devuelve el resultado.
    """

    # --- Implementaciones internas de cada herramienta ---
    def _listar_directorio():
        # Obtenemos la ruta segura, si no se pasa nada usamos "." (directorio actual)
        path = ruta_segura(arguments.get("ruta", "."))
        if not path.exists():
            return f"Error: '{arguments.get('ruta')}' no existe."
        
        # Iteramos el directorio y ordenamos: primero archivos, luego directorios (alfabéticamente)
        items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not items:
            return "Directorio vacio."
        
        # Construimos la salida en texto
        lineas = [f"Contenido de: {path.relative_to(BASE_DIR) if path != BASE_DIR else '.'}"]
        for item in items:
            tipo = "[DIR] " if item.is_dir() else "[FILE]"
            tamaño = f"  ({item.stat().st_size:,} bytes)" if item.is_file() else ""
            lineas.append(f"  {tipo} {item.name}{tamaño}")
        return "\n".join(lineas)

    def _leer_archivo():
        # Lee el contenido de texto de un archivo
        path = ruta_segura(arguments["ruta"])
        if not path.exists():
            return f"Error: '{arguments['ruta']}' no existe."
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "Error: archivo binario no legible como texto."

    def _escribir_archivo():
        # Escribe contenido en un archivo. Crea las carpetas intermedias si no existen.
        path = ruta_segura(arguments["ruta"])
        path.parent.mkdir(parents=True, exist_ok=True)
        accion = "actualizado" if path.exists() else "creado"
        path.write_text(arguments["contenido"], encoding="utf-8")
        return f"Archivo {accion}: {path.relative_to(BASE_DIR)}"

    def _info_archivo():
        # Obtiene metadatos (tipo, tamaño, fecha de modificación)
        path = ruta_segura(arguments["ruta"])
        if not path.exists():
            return f"Error: '{arguments['ruta']}' no existe."
        from datetime import datetime
        stat = path.stat()
        modificado = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"Nombre:     {path.name}\n"
            f"Tipo:       {'Directorio' if path.is_dir() else 'Archivo'}\n"
            f"Tamaño:     {stat.st_size:,} bytes\n"
            f"Modificado: {modificado}"
        )

    # Diccionario que mapea el nombre de la herramienta a su función interna
    acciones = {
        "listar_directorio": _listar_directorio,
        "leer_archivo": _leer_archivo,
        "escribir_archivo": _escribir_archivo,
        "info_archivo": _info_archivo,
    }

    # Validamos que la herramienta solicitada exista
    if nombre not in acciones:
        return [TextContent(type="text", text=f"Herramienta desconocida: {nombre}")]

    try:
        # Ejecutamos la función sincrónica de archivos en un hilo separado (para no bloquear el bucle asíncrono)
        texto = await asyncio.to_thread(acciones[nombre])
    except PermissionError as e:
        texto = str(e)  # Error de seguridad (ruta fuera de BASE_DIR)
    except Exception as e:
        texto = f"Error: {e}"

    # Retornamos el resultado en el formato TextContent requerido por MCP
    return [TextContent(type="text", text=texto)]


# ── SSE Transport (Compatible con App Service) ────────────────────────────────
# Creamos el transporte SSE indicando que las peticiones POST irán a "/messages/"
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    """
    Endpoint (GET /sse): Maneja la conexión inicial persistente Server-Sent Events.
    Mantiene abierta la conexión para enviar mensajes del servidor al cliente.
    """
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        # Inicializa la aplicación MCP pasándole los flujos de lectura y escritura del SSE
        await mcp_app.run(
            streams[0], streams[1], mcp_app.create_initialization_options()
        )

async def handle_health(request: Request):
    """
    Endpoint (GET /): Utilizado para comprobar si el servidor está encendido (Healthcheck).
    """
    return JSONResponse({"status": "ok", "message": "MCP Server running"})

# Aplicación Starlette principal con las rutas estándar
starlette_app = Starlette(debug=True, routes=[
    Route("/", handle_health),
    Route("/sse", handle_sse),
])

async def app(scope, receive, send):
    """
    Aplicación ASGI principal o Entrypoint.
    Azure App Service (vía Gunicorn) lanzará automáticamente este objeto 'app'.
    Se encarga de interceptar los POST a '/messages/' y enrutarlos directamente
    al transporte SSE, sin pasar por las rutas de Starlette (para evitar que se corte el path).
    """
    if scope["type"] == "http":
        path = scope.get("path", "")
        # Si el path es el de mensajes, enviamos el scope asíncrono directo al transporte SSE
        if path == "/messages/":
            await sse_transport.handle_post_message(scope, receive, send)
            return
    # Si no es un mensaje MCP, pasamos la petición al router de Starlette
    await starlette_app(scope, receive, send)


# ── Modo Local (Stdio) ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from mcp.server.stdio import stdio_server
    
    async def main():
        """
        Si este script se ejecuta desde la terminal (python app.py),
        levantamos el servidor usando la entrada/salida estándar (stdio)
        en lugar de un puerto HTTP. Útil para pruebas locales sin internet.
        """
        async with stdio_server() as (read, write):
            await mcp_app.run(read, write, mcp_app.create_initialization_options())
            
    asyncio.run(main())
