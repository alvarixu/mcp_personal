import asyncio
import sys
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def iniciar_cliente():
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["server.py"]
    )

    print("Conectando al servidor MCP...")

    async with stdio_client(server_parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("¡Conexión establecida con éxito!")

            # Listar herramientas disponibles
            herramientas = await session.list_tools()
            print("\n--- Herramientas Disponibles ---")
            for tool in herramientas.tools:
                print(f"- {tool.name}: {tool.description}")

            # ── Prueba 1: listar directorio raíz ─────────────────────────
            print("\n[1] Listando directorio raíz...")
            r = await session.call_tool("listar_directorio", arguments={"ruta": "."})
            print(r.content[0].text)

            # ── Prueba 2: crear un archivo ────────────────────────────────
            print("\n[2] Creando archivo de prueba...")
            r = await session.call_tool("escribir_archivo", arguments={
                "ruta": "prueba/hola.txt",
                "contenido": "Hola desde el servidor MCP!\nEste archivo fue creado automaticamente."
            })
            print(r.content[0].text)

            # ── Prueba 3: leer el archivo creado ──────────────────────────
            print("\n[3] Leyendo archivo creado...")
            r = await session.call_tool("leer_archivo", arguments={"ruta": "prueba/hola.txt"})
            print(r.content[0].text)

            # ── Prueba 4: info del archivo ────────────────────────────────
            print("\n[4] Info del archivo...")
            r = await session.call_tool("info_archivo", arguments={"ruta": "prueba/hola.txt"})
            print(r.content[0].text)

            # ── Prueba 5: listar subdirectorio creado ─────────────────────
            print("\n[5] Listando carpeta 'prueba'...")
            r = await session.call_tool("listar_directorio", arguments={"ruta": "prueba"})
            print(r.content[0].text)

            # ── Prueba 6: eliminar archivo ────────────────────────────────
            print("\n[6] Eliminando archivo de prueba...")
            r = await session.call_tool("eliminar_archivo", arguments={"ruta": "prueba/hola.txt"})
            print(r.content[0].text)

            print("\nTodas las pruebas completadas.")

if __name__ == "__main__":
    try:
        asyncio.run(iniciar_cliente())
    except KeyboardInterrupt:
        print("\nCliente detenido por el usuario.")
    except Exception as e:
        print(f"Error al comunicarse con el servidor MCP: {e}")