"""FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.errors import ERROR_CATALOG, APIError, api_error_handler, validation_exception_handler
from app.core.settings import settings

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description=(
            "Agent-first async transcription API. Submit video/audio, poll for structured "
            "speaker-diarized JSON (Whisper + Chirp 3 + Gemini). Designed for LLMs and autonomous agents."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)

    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/keys", include_in_schema=False)
    def keys_ui():
        html = STATIC_DIR / "keys.html"
        if html.exists():
            return HTMLResponse(html.read_text(encoding="utf-8"))
        return HTMLResponse("<p>keys.html missing</p>")

    @app.get("/llms.txt", include_in_schema=False)
    def llms_txt():
        path = PUBLIC_DIR / "llms.txt"
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain")

    @app.get("/.well-known/agent.json", include_in_schema=False)
    def well_known_agent():
        path = PUBLIC_DIR / ".well-known" / "agent.json"
        return JSONResponse(content=__import__("json").loads(path.read_text(encoding="utf-8")))

    @app.get("/.well-known/ai-plugin.json", include_in_schema=False)
    def well_known_plugin():
        path = PUBLIC_DIR / ".well-known" / "ai-plugin.json"
        return JSONResponse(content=__import__("json").loads(path.read_text(encoding="utf-8")))

    @app.get("/docs/errors", include_in_schema=False)
    def error_docs():
        rows = "".join(
            f"<tr><td><code>{e['code']}</code></td><td>{e['description']}</td>"
            f"<td>{e['suggested_action']}</td></tr>"
            for e in ERROR_CATALOG
        )
        return HTMLResponse(f"""
        <html><head><title>Error codes</title></head><body>
        <h1>Agent error codes</h1>
        <table border="1" cellpadding="8"><tr><th>Code</th><th>Description</th><th>Action</th></tr>
        {rows}</table></body></html>
        """)

    @app.get("/sdk/python/README.md", include_in_schema=False)
    def sdk_readme():
        return FileResponse(Path("sdk") / "README.md")

    app.openapi = lambda: _custom_openapi(app)
    return app


async def _http_handler(request: Request, exc: StarletteHTTPException):
    from app.core.errors import http_exception_handler
    return await http_exception_handler(request, exc)


def _custom_openapi(app: FastAPI) -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["info"]["x-agent-optimized"] = True
    schema["info"]["contact"] = {"name": "Transcription API", "url": settings.BASE_URL}
    schema["servers"] = [{"url": settings.BASE_URL, "description": "Primary"}]
    # Must match FastAPI's HTTPBearer scheme name — do not use a different name (Swagger won't send the header).
    _auth_description = (
        "Paste ONLY your API key (starts with tx_). Do NOT type the word Bearer. "
        "Create a key at /keys or POST /api/v1/keys/bootstrap (header X-Admin-Secret)."
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["HTTPBearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "API key",
        "description": _auth_description,
    }
    for path_item in schema.get("paths", {}).values():
        for method in path_item.values():
            if isinstance(method, dict) and method.get("security"):
                method["security"] = [{"HTTPBearer": []}]
    schema["paths"]["/api/v1/transcriptions"]["post"]["requestBody"] = {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "format": "binary"},
                        "webhook_url": {"type": "string"},
                        "model": {"type": "string"},
                    },
                    "required": ["file"],
                }
            }
        }
    }
    app.openapi_schema = schema
    return schema


app = create_app()
