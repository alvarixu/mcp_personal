# MCP Personal Server

Este es un servidor personal basado en el [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol), diseñado para exponer de forma segura y controlada el sistema de archivos (lectura, escritura y metadatos) a modelos de IA. 

El servidor puede ejecutarse de manera **local** (a través de la entrada y salida estándar `stdio`) o desplegarse en la nube en **Azure App Service** mediante Server-Sent Events (SSE).

## 🚀 Características y Herramientas Incluidas

El servidor expone 4 herramientas principales:
- `listar_directorio`: Muestra el contenido de una ruta (archivos, subcarpetas y tamaños).
- `leer_archivo`: Extrae el texto de un archivo específico.
- `escribir_archivo`: Crea o sobrescribe un archivo con nuevo contenido.
- `info_archivo`: Proporciona detalles como la última fecha de modificación, tipo y tamaño exacto en bytes.

Cuenta con protección integrada de seguridad (`ruta_segura`) para garantizar que la IA solo pueda interactuar con archivos dentro del directorio base de este proyecto.

## 📂 Estructura del Proyecto

- `app.py`: El código principal del servidor MCP. Contiene la lógica de las herramientas y soporta conexiones ASGI/SSE para la nube, además de contar con ejecución local (Stdio).
- `client.py`: Script de prueba asíncrono para conectarse a tu propio servidor (ya sea en local o en Azure) y ejecutar herramientas de demostración.
- `requirements.txt`: Dependencias de Python (`mcp[sse]`, `starlette`, `uvicorn`).
- `.env`: Variables de entorno como la URL de tu Azure App Service y el modo en que quieres que se conecte el script de cliente.

## ⚙️ Uso en Entorno Local (Stdio)

Si quieres usar el servidor localmente (por ejemplo, para probar en tu terminal sin necesidad de conexión a internet):

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Asegúrate de que en tu archivo `.env` tengas configurado el modo local:
   ```env
   MCP_MODO=local
   ```
3. Ejecuta el cliente para comprobar la conexión:
   ```bash
   python client.py
   ```

## ☁️ Despliegue en Azure App Service

El código está optimizado para funcionar sobre Azure App Service usando Gunicorn/Uvicorn, ya que MCP necesita mantener conexiones largas y memoria persistente, lo cual las arquitecturas serverless clásicas (como Azure Functions Consumption Plan) no soportan correctamente.

Para desplegarlo a Azure:

1. Asegúrate de estar autenticado en Azure CLI:
   ```bash
   az login
   ```
2. Ejecuta el comando de subida indicando tu nombre, grupo de recursos y el nivel (SKU) del servicio (ejemplo con F1 gratuito):
   ```bash
   az webapp up --name mcppersonal-app-alvaro --resource-group LopezRedondoAlvaro --runtime "PYTHON:3.11" --sku F1
   ```
3. Activa el Worker asíncrono en Azure para que Starlette (ASGI) maneje correctamente el streaming:
   ```bash
   az webapp config set --resource-group LopezRedondoAlvaro --name mcppersonal-app-alvaro --startup-file "gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app"
   ```
4. Actualiza tu `.env` para que apunte a Azure:
   ```env
   MCP_MODO=azure
   MCP_AZURE_URL=https://mcppersonal-app-alvaro.azurewebsites.net/sse
   ```
5. ¡Lanza `python client.py` y verás la conexión contra tu nube!
