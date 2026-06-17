import asyncio
import sys
import os
from pathlib import Path

# Carga variables de entorno desde .env
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Carga la configuración del entorno (como MCP_MODO y MCP_AZURE_URL)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ── Transporte SSE (servidor remoto en Azure App Service) ─────────────────────
# Importamos sse_client de forma segura por si la librería no está instalada
try:
    from mcp.client.sse import sse_client
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

# ── Configuración ─────────────────────────────────────────────────────────────
# Obtenemos el modo (por defecto 'local' si no se especifica en el .env)
MODO = os.getenv("MCP_MODO", "local")

# Obtenemos la URL de Azure App Service a la que conectarse en modo 'azure'
AZURE_MCP_URL = os.getenv("MCP_AZURE_URL", "https://mcp-personal-app.azurewebsites.net/sse")

# ── Cliente local (stdio) ─────────────────────────────────────────────────────
async def conectar_local():
    """
    Se conecta al servidor MCP levantando un subproceso local de Python
    que ejecuta `app.py`. Utiliza la entrada y salida estándar (stdio) para
    comunicarse. No necesita conexión a internet ni un servidor web.
    """
    server_parameters = StdioServerParameters(
        command=sys.executable,  # Usa el ejecutable actual de Python
        args=["app.py"]          # Script a ejecutar que levanta el servidor stdio
    )
    # Inicializa el cliente stdio y obtiene los flujos de lectura y escritura
    async with stdio_client(server_parameters) as (read, write):
        # Inicia una sesión de cliente MCP estándar usando esos flujos
        async with ClientSession(read, write) as session:
            await ejecutar_sesion(session)

# ── Cliente Azure (SSE) ───────────────────────────────────────────────────────
async def conectar_azure():
    """
    Se conecta al servidor MCP alojado remotamente en Azure App Service.
    Utiliza el protocolo Server-Sent Events (SSE) para mantener la comunicación
    abierta e intercambiar mensajes JSON RPC bidireccionalmente vía HTTP.
    """
    if not SSE_AVAILABLE:
        print("Error: El cliente sse no está disponible. pip install mcp[sse]")
        return
        
    print(f"Conectando a Azure MCP: {AZURE_MCP_URL}")
    
    # Inicializa la conexión web (SSE) y obtiene los flujos asíncronos
    async with sse_client(AZURE_MCP_URL) as (read, write):
        # Abre la sesión sobre esos flujos, igual que en el modo local
        async with ClientSession(read, write) as session:
            await ejecutar_sesion(session)


# ── Lógica común de sesión ────────────────────────────────────────────────────
async def ejecutar_sesion(session: ClientSession):
    """
    Esta función contiene la lógica principal del script cliente.
    Es agnóstica al transporte: funciona exactamente igual independientemente
    de si la sesión (`session`) proviene de stdio local o SSE en la nube.
    """
    
    # El handshake de inicialización es obligatorio en MCP antes de mandar peticiones
    await session.initialize()
    print("¡Conexión establecida con éxito!")

    # Petición: Listar las herramientas (Tools) disponibles que ofrece el servidor
    herramientas = await session.list_tools()
    print("\n--- Herramientas Disponibles ---")
    for tool in herramientas.tools:
        print(f"- {tool.name}: {tool.description}")

    # ── Prueba: listar directorio raíz ─────────────────────────────────────────
    # Verificamos si el servidor nos ha ofrecido la herramienta "listar_directorio"
    if any(t.name == "listar_directorio" for t in herramientas.tools):
        print("\n[TEST] Listando directorio raíz...")
        # Solicitamos la ejecución de la herramienta con argumentos en formato JSON
        r = await session.call_tool("listar_directorio", arguments={"ruta": "."})
        # Imprimimos la respuesta recibida desde el servidor
        print(r.content[0].text)
    else:
        print("\n[INFO] El servidor no tiene 'listar_directorio'. Herramientas listadas arriba.")


# ── Punto de entrada ──────────────────────────────────────────────────────────
async def main():
    """
    Lanzador principal que decide a qué tipo de servidor conectarse
    en base a la variable MODO del archivo .env.
    """
    print(f"Modo: {MODO.upper()}")
    if MODO == "azure":
        await conectar_azure()
    else:
        await conectar_local()


if __name__ == "__main__":
    # Arranca el bucle de eventos asíncronos de Python
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Captura Control+C de forma limpia
        print("\nCliente detenido.")
    except Exception as e:
        # Si algo falla gravemente, mostramos la traza completa (útil para depurar)
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")