import asyncio
import sys
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def iniciar_cliente():
    # 1. Configurar los parámetros del servidor
    # Definimos el comando y los argumentos para ejecutar el servidor MCP local.
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["server.py"]
    )

    print("Conectando al servidor MCP...")

    # 2. Iniciar el transporte stdio usando un gestor de contexto asíncrono
    async with stdio_client(server_parameters) as (read_stream, write_stream):
        
        # 3. Crear la sesión del cliente con los streams de lectura y escritura
        async with ClientSession(read_stream, write_stream) as session:
            
            # 4. Inicializar la conexión con el servidor
            await session.initialize()
            print("¡Conexión establecida con éxito!")

            # 5. Listar las herramientas (tools) disponibles en el servidor
            herramientas = await session.list_tools()
            print("\n--- Herramientas Disponibles ---")
            for tool in herramientas.tools:
                print(f"- {tool.name}: {tool.description}")

            # ── Prueba 1: listar_repos ────────────────────────────────────
            print("\nEjecutando 'listar_repos'...")
            r = await session.call_tool("listar_repos", arguments={})
            print("\n--- Tus Repositorios ---")
            print(r.content[0].text)

            # ── Prueba 2: info_repo ───────────────────────────────────────
            print("\nEjecutando 'info_repo' sobre alvarixu/mcp_personal...")
            r = await session.call_tool("info_repo", arguments={"nombre_repo": "alvarixu/mcp_personal"})
            print("\n--- Info del Repo ---")
            print(r.content[0].text)

            # ── Prueba 3: listar_issues ───────────────────────────────────
            print("\nEjecutando 'listar_issues' sobre alvarixu/mcp_personal...")
            r = await session.call_tool("listar_issues", arguments={"nombre_repo": "alvarixu/mcp_personal", "estado": "all"})
            print("\n--- Issues ---")
            print(r.content[0].text)

            # ── Prueba 4: crear_issue ─────────────────────────────────────
            print("\nEjecutando 'crear_issue' sobre alvarixu/TFG...")
            r = await session.call_tool("crear_issue", arguments={
                "nombre_repo": "alvarixu/TFG",
                "titulo": "Issue de prueba creado via MCP",
                "cuerpo": "Este issue fue creado automaticamente por el servidor MCP local."
            })
            print("\n--- Issue Creado ---")
            print(r.content[0].text)

if __name__ == "__main__":
    # Ejecutar el bucle de eventos asíncrono de Python
    try:
        asyncio.run(iniciar_cliente())
    except KeyboardInterrupt:
        print("\nCliente detenido por el usuario.")
    except Exception as e:
        print(f"Error al comunicarse con el servidor MCP: {e}")