import asyncio
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from github import Github
from dotenv import load_dotenv

load_dotenv()

# ── Inicializar servidor MCP ──────────────────────────────────────────────────
app = Server("mcp-github-personal")

def get_github_client() -> Github:
    """Retorna un cliente de GitHub autenticado con el PAT del entorno."""
    token = os.getenv("GITHUB_PAT")
    if not token:
        raise ValueError("Variable de entorno GITHUB_PAT no definida. Crea un archivo .env con GITHUB_PAT=tu_token")
    return Github(token)


# ── Definición de herramientas ────────────────────────────────────────────────
@app.list_tools()
async def listar_herramientas() -> list[Tool]:
    return [
        Tool(
            name="listar_repos",
            description="Lista todos los repositorios del usuario autenticado con GitHub PAT.",
            inputSchema={
                "type": "object",
                "properties": {
                    "solo_privados": {
                        "type": "boolean",
                        "description": "Si es true, solo devuelve repositorios privados.",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="info_repo",
            description="Obtiene información detallada de un repositorio específico.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_repo": {
                        "type": "string",
                        "description": "Nombre completo del repo en formato 'usuario/repo'."
                    }
                },
                "required": ["nombre_repo"]
            }
        ),
        Tool(
            name="listar_issues",
            description="Lista los issues abiertos de un repositorio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_repo": {
                        "type": "string",
                        "description": "Nombre completo del repo en formato 'usuario/repo'."
                    },
                    "estado": {
                        "type": "string",
                        "description": "Estado de los issues: 'open', 'closed' o 'all'.",
                        "default": "open"
                    }
                },
                "required": ["nombre_repo"]
            }
        ),
        Tool(
            name="crear_issue",
            description="Crea un nuevo issue en un repositorio.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_repo": {
                        "type": "string",
                        "description": "Nombre completo del repo en formato 'usuario/repo'."
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Título del issue."
                    },
                    "cuerpo": {
                        "type": "string",
                        "description": "Descripción/cuerpo del issue.",
                        "default": ""
                    }
                },
                "required": ["nombre_repo", "titulo"]
            }
        ),
    ]


# ── Implementación de herramientas ────────────────────────────────────────────
@app.call_tool()
async def ejecutar_herramienta(nombre: str, arguments: dict) -> list[TextContent]:

    def _listar_repos():
        gh = get_github_client()
        solo_privados = arguments.get("solo_privados", False)
        usuario = gh.get_user()
        repos = list(usuario.get_repos())
        resultado = []
        for repo in repos:
            if solo_privados and not repo.private:
                continue
            visibilidad = "Privado" if repo.private else "Publico"
            resultado.append(f"{visibilidad} | {repo.full_name} - Stars: {repo.stargazers_count}")
        return "\n".join(resultado) if resultado else "No se encontraron repositorios."

    def _info_repo():
        gh = get_github_client()
        repo = gh.get_repo(arguments["nombre_repo"])
        return (
            f"Repositorio: {repo.full_name}\n"
            f"Descripcion: {repo.description or 'Sin descripcion'}\n"
            f"URL: {repo.html_url}\n"
            f"Stars: {repo.stargazers_count}\n"
            f"Forks: {repo.forks_count}\n"
            f"Privado: {'Si' if repo.private else 'No'}\n"
            f"Rama principal: {repo.default_branch}\n"
            f"Creado: {repo.created_at.strftime('%Y-%m-%d')}\n"
            f"Ultimo push: {repo.pushed_at.strftime('%Y-%m-%d') if repo.pushed_at else 'N/A'}"
        )

    def _listar_issues():
        gh = get_github_client()
        estado = arguments.get("estado", "open")
        repo = gh.get_repo(arguments["nombre_repo"])
        issues = list(repo.get_issues(state=estado))
        resultado = [f"#{i.number} | {i.title} ({i.state})" for i in issues]
        return "\n".join(resultado) if resultado else "No hay issues."

    def _crear_issue():
        gh = get_github_client()
        repo = gh.get_repo(arguments["nombre_repo"])
        issue = repo.create_issue(
            title=arguments["titulo"],
            body=arguments.get("cuerpo", "")
        )
        return f"Issue creado: #{issue.number} - {issue.title}\n{issue.html_url}"

    acciones = {
        "listar_repos": _listar_repos,
        "info_repo": _info_repo,
        "listar_issues": _listar_issues,
        "crear_issue": _crear_issue,
    }

    if nombre not in acciones:
        return [TextContent(type="text", text=f"Herramienta desconocida: {nombre}")]

    # Ejecutar la llamada bloqueante de PyGithub en un hilo separado
    texto = await asyncio.to_thread(acciones[nombre])
    return [TextContent(type="text", text=texto)]


# ── Punto de entrada ──────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
