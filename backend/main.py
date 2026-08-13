import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import database
import reminder_jobs
from deps import UPLOADS_DIR
from auth_reset import reset_router
from routers import auth_routes, admin_routes, catalog_routes, quiz_routes, student_routes

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    """Inicializa o banco de dados e o agendador de lembretes por e-mail
    (certificado vencendo, curso parado) ao subir o servidor."""
    database.init_db()
    reminder_jobs.start_scheduler()
    yield
    reminder_jobs.stop_scheduler()

app = FastAPI(title="GeoTrilha LMS API", lifespan=lifespan)

# CORS Configuration — nega por padrão em vez de liberar geral quando não
# configurado. Se ALLOWED_ORIGINS não estiver definida, usa BASE_URL (a
# única origem que esta app realmente espera servir); se nem isso existir,
# fica sem nenhuma origem liberada.
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if "" in origins: origins.remove("")
if not origins:
    base_url = os.getenv("BASE_URL", "").strip()
    if base_url:
        origins = [base_url]
    else:
        print("AVISO: ALLOWED_ORIGINS e BASE_URL não definidas — nenhuma origem cross-site será liberada pela API.")
        origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False, # Credentials not allowed with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reset_router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(catalog_routes.router)
app.include_router(quiz_routes.router)
app.include_router(student_routes.router)

# Cache Middleware for Static Assets
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/uploads"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif request.url.path.endswith((".js", ".css", ".ico")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
print(f"DEBUG: Serving frontend from: {frontend_path}")

@app.get("/")
async def serve_index():
    index_path = os.path.join(frontend_path, "index.html")
    print(f"DEBUG: Index requested. Path: {index_path} - Exists: {os.path.exists(index_path)}")
    if os.path.exists(index_path):
        from fastapi.responses import FileResponse
        return FileResponse(index_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"message": "Frontend not found"}

# Caminhos corrigidos para a raiz do projeto
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/video", StaticFiles(directory=UPLOADS_DIR), name="video")

if os.path.exists(frontend_path):
    # Mount everything else EXCEPT the root which is handled by serve_index
    app.mount("/", StaticFiles(directory=frontend_path, html=False), name="frontend")

if __name__ == "__main__":
    database.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
