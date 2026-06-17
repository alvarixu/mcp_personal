import asyncio
import os
import shutil
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Inicializar servidor MCP ──────────────────────────────────────────────────
app = Server("mcp-filesystem")

# Directorio raíz permitido (carpeta del propio proyecto)
BASE_DIR = Path(__file__).parent.resolve()


def ruta_segura(ruta: str) -> Path:
    """Resuelve la ruta y verifica que esté dentro de BASE_DIR."""
    path = (BASE_DIR / ruta).resolve()
    if not str(path).startswith(str(BASE_DIR)):
        raise PermissionError(f"Acceso denegado: '{ruta}' está fuera del directorio permitido.")
    return path


# ── Definición de herramientas ────────────────────────────────────────────────
@app.list_tools()
async def listar_herramientas() -> list[Tool]:
    return [
        Tool(
            name="listar_directorio",
            description="Lista el contenido de un directorio (archivos y subcarpetas).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al directorio base del proyecto. Usa '.' para la raíz.",
                        "default": "."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="leer_archivo",
            description="Lee y devuelve el contenido de un archivo de texto.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al archivo dentro del directorio base."
                    }
                },
                "required": ["ruta"]
            }
        ),
        Tool(
            name="escribir_archivo",
            description="Crea o sobreescribe un archivo con el contenido proporcionado.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al archivo a crear/sobreescribir."
                    },
                    "contenido": {
                        "type": "string",
                        "description": "Texto a escribir en el archivo."
                    }
                },
                "required": ["ruta", "contenido"]
            }
        ),
        Tool(
            name="eliminar_archivo",
            description="Elimina un archivo existente.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al archivo a eliminar."
                    }
                },
                "required": ["ruta"]
            }
        ),
        Tool(
            name="crear_directorio",
            description="Crea un nuevo directorio (y subdirectorios si es necesario).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al directorio a crear."
                    }
                },
                "required": ["ruta"]
            }
        ),
        Tool(
            name="info_archivo",
            description="Devuelve metadatos de un archivo o directorio (tamaño, fecha de modificación, tipo).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruta": {
                        "type": "string",
                        "description": "Ruta relativa al archivo o directorio."
                    }
                },
                "required": ["ruta"]
            }
        ),
    ]


# ── Implementación de herramientas ────────────────────────────────────────────
@app.call_tool()
async def ejecutar_herramienta(nombre: str, arguments: dict) -> list[TextContent]:

    def _listar_directorio():
        path = ruta_segura(arguments.get("ruta", "."))
        if not path.exists():
            return f"Error: '{path}' no existe."
        if not path.is_dir():
            return f"Error: '{path}' no es un directorio."
        items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not items:
            return "Directorio vacío."
        lineas = [f"Contenido de: {path.relative_to(BASE_DIR) if path != BASE_DIR else '.'}"]
        for item in items:
            tipo = "[DIR] " if item.is_dir() else "[FILE]"
            tamaño = f"  ({item.stat().st_size:,} bytes)" if item.is_file() else ""
            lineas.append(f"  {tipo} {item.name}{tamaño}")
        return "\n".join(lineas)

    def _leer_archivo():
        path = ruta_segura(arguments["ruta"])
        if not path.exists():
            return f"Error: '{arguments['ruta']}' no existe."
        if not path.is_file():
            return f"Error: '{arguments['ruta']}' no es un archivo."
        try:
            contenido = path.read_text(encoding="utf-8")
            lineas = len(contenido.splitlines())
            return f"--- {path.name} ({lineas} líneas) ---\n{contenido}"
        except UnicodeDecodeError:
            return f"Error: '{arguments['ruta']}' es un archivo binario y no se puede leer como texto."

    def _escribir_archivo():
        path = ruta_segura(arguments["ruta"])
        path.parent.mkdir(parents=True, exist_ok=True)
        accion = "actualizado" if path.exists() else "creado"
        path.write_text(arguments["contenido"], encoding="utf-8")
        return f"Archivo {accion}: {path.relative_to(BASE_DIR)} ({path.stat().st_size:,} bytes escritos)"

    def _eliminar_archivo():
        path = ruta_segura(arguments["ruta"])
        if not path.exists():
            return f"Error: '{arguments['ruta']}' no existe."
        if path.is_dir():
            shutil.rmtree(path)
            return f"Directorio eliminado: {arguments['ruta']}"
        path.unlink()
        return f"Archivo eliminado: {arguments['ruta']}"

    def _crear_directorio():
        path = ruta_segura(arguments["ruta"])
        if path.exists():
            return f"Ya existe: {arguments['ruta']}"
        path.mkdir(parents=True, exist_ok=True)
        return f"Directorio creado: {arguments['ruta']}"

    def _info_archivo():
        path = ruta_segura(arguments["ruta"])
        if not path.exists():
            return f"Error: '{arguments['ruta']}' no existe."
        stat = path.stat()
        from datetime import datetime
        modificado = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        tipo = "Directorio" if path.is_dir() else "Archivo"
        tamaño = f"{stat.st_size:,} bytes" if path.is_file() else "N/A"
        return (
            f"Nombre:      {path.name}\n"
            f"Tipo:        {tipo}\n"
            f"Tamaño:      {tamaño}\n"
            f"Modificado:  {modificado}\n"
            f"Ruta:        {path.relative_to(BASE_DIR)}"
        )

    acciones = {
        "listar_directorio": _listar_directorio,
        "leer_archivo":      _leer_archivo,
        "escribir_archivo":  _escribir_archivo,
        "eliminar_archivo":  _eliminar_archivo,
        "crear_directorio":  _crear_directorio,
        "info_archivo":      _info_archivo,
    }

    if nombre not in acciones:
        return [TextContent(type="text", text=f"Herramienta desconocida: {nombre}")]

    try:
        texto = await asyncio.to_thread(acciones[nombre])
    except PermissionError as e:
        texto = f"Permiso denegado: {e}"
    except Exception as e:
        texto = f"Error: {e}"

    return [TextContent(type="text", text=texto)]


# ── Punto de entrada ──────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
