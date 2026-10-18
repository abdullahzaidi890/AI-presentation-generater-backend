import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db.database import init_db
from .routers.api import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="AI Presentation Generator (local single-user mode)")
    init_db()

    origins = {s.frontend_origin, s.frontend_origin.replace("localhost", "127.0.0.1")}
    app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Content-Type"])

    max_body = (s.max_upload_mb + 1) * 1024 * 1024

    @app.middleware("http")
    async def limit_size(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > max_body:
            return JSONResponse({"detail": "Request is too large."}, status_code=413)
        return await call_next(request)

    @app.exception_handler(Exception)
    async def generic(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)  # details only in the server log
        return JSONResponse({"detail": "Internal server error."}, status_code=500)

    app.include_router(router)
    return app


app = create_app()
