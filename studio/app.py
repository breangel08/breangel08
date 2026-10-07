import hmac
import json
import mimetypes
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from engine import assets
from engine.models import Brief, Review, FinalApproval, WebsiteType, Target, ROLES
from engine.service import Engine
from engine.store import Store, Conflict

STATIC = Path(__file__).parent / "static"


class Resolution(BaseModel):
    resolution: str = Field(max_length=2000)
    patches: dict | None = None


class AssetRole(BaseModel):
    role: str


class Session(BaseModel):
    token: str = Field(max_length=500)


def create_app(data_dir=None):
    engine = Engine(Store(data_dir))
    @asynccontextmanager
    async def lifespan(app):
        engine.recover_jobs()
        yield
        engine.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Website Production Engine", version="1.0.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.sessions = {}
    app.state.login_attempts = {}
    app.state.previews = {}

    @app.middleware("http")
    async def authority_security(request: Request, call_next):
        path = request.url.path
        token = os.getenv("STUDIO_TOKEN")
        public = path in {"/", "/api/health", "/api/session"} or path.startswith(("/static/", "/preview/"))
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            declared = request.headers.get("Content-Length")
            maximum = (int(os.getenv("STUDIO_MAX_UPLOAD_MB", "25")) + 1) * 1024 * 1024
            if declared:
                try:
                    length = int(declared)
                except ValueError:
                    return JSONResponse({"error": "INVALID_LENGTH", "message": "Invalid request size"}, status_code=400)
                if length < 0 or length > maximum:
                    return JSONResponse({"error": "REQUEST_TOO_LARGE", "message": "Request exceeds the workspace upload limit"}, status_code=413)
            elif request.headers.get("Transfer-Encoding"):
                return JSONResponse({"error": "LENGTH_REQUIRED", "message": "Provide Content-Length for bounded workspace requests"}, status_code=411)
        if not public:
            supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if token:
                session = request.cookies.get("studio_session", "")
                if not hmac.compare_digest(supplied, token) and app.state.sessions.get(session, 0) <= time.time():
                    return JSONResponse({"error": "AUTH_REQUIRED", "message": "Sign in to your production workspace"}, status_code=401)
            elif request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                return JSONResponse({"error": "LOCAL_ONLY", "message": "Configure STUDIO_TOKEN before exposing the Studio to a network"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.headers.get("Host"):
                return JSONResponse({"error": "ORIGIN_REJECTED", "message": "Cross-origin mutations are not permitted"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers["Cache-Control"] = "no-store" if not path.startswith("/static/") else "public, max-age=3600"
        if not path.startswith("/preview/") and (not path.startswith("/api/projects/") or "/files/" not in path):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        return response

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse({"error": "STATE_CONFLICT", "message": str(error)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"error": "NOT_FOUND", "message": str(error).strip("'")}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"error": "INVALID_OPERATION", "message": str(error)}, status_code=422)

    @app.exception_handler(Exception)
    async def failed(request, error):
        return JSONResponse({"error": "OPERATION_FAILED", "message": "The operation could not complete. Your project state is preserved; use recovery to verify the next operation."}, status_code=500)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "engine_version": "1.0.0", "auth_required": bool(os.getenv("STUDIO_TOKEN"))}

    @app.post("/api/session")
    def login(value: Session, request: Request):
        stamp = time.time()
        client = request.client.host if request.client else "unknown"
        recent = [t for t in app.state.login_attempts.get(client, []) if stamp - t < 60]
        if len(recent) >= 10:
            raise HTTPException(429, "Too many sign-in attempts; try again in a minute")
        app.state.login_attempts[client] = recent + [stamp]
        token = os.getenv("STUDIO_TOKEN", "")
        if not token or not hmac.compare_digest(value.token, token):
            raise HTTPException(401, "Invalid workspace token")
        session = secrets.token_urlsafe(32)
        app.state.sessions = {key: expiry for key, expiry in app.state.sessions.items() if expiry > stamp}
        app.state.sessions[session] = stamp + 28800
        response = JSONResponse({"authenticated": True})
        response.set_cookie("studio_session", session, httponly=True, secure=request.url.scheme == "https", samesite="strict", max_age=28800)
        return response

    @app.get("/api/catalog")
    def catalog():
        return {"website_types": [t.value for t in WebsiteType], "targets": [t.value for t in Target], "roles": ROLES, "engine_version": "1.0.0", "autonomy_level": 5}

    @app.get("/api/projects")
    def projects():
        return [{"id": p["id"], "name": p["name"], "classification": p["classification"], "stage": p["stage"], "stage_status": p["stage_status"], "updated_at": p["updated_at"], "fixture": p["fixture"], "status": engine.status(p), "active_design": p["active_design"], "preview": p["design_versions"][p["active_design"] - 1]["capture_path"] + "/home-laptop.png" if p["active_design"] and p["design_versions"][p["active_design"] - 1]["captures"]["status"] == "PASS" else None} for p in engine.store.list()]

    @app.post("/api/projects", status_code=201)
    def create(brief: Brief):
        return engine.contextual(engine.create(brief))

    @app.get("/api/projects/{project_id}")
    def project(project_id: str):
        value = engine.contextual(engine.store.get(project_id))
        stamp = time.time()
        app.state.previews = {k: v for k, v in app.state.previews.items() if v["expires"] > stamp}
        roots = {}
        if value["active_design"]:
            roots["visual"] = value["design_versions"][value["active_design"] - 1]["prototype_path"]
        if value["release_candidate"]:
            roots["final"] = next(b["path"] for b in value["builds"] if b["id"] == value["release_candidate"]["build_id"])
        value["preview_urls"] = {}
        for name, relative in roots.items():
            root = (engine.store.path(project_id) / relative).resolve()
            grant = next((k for k, v in app.state.previews.items() if v["root"] == root), None)
            if not grant:
                if len(app.state.previews) >= 1024:
                    app.state.previews.pop(next(iter(app.state.previews)))
                grant = secrets.token_urlsafe(32)
                app.state.previews[grant] = {"root": root, "expires": stamp + 28800}
            value["preview_urls"][name] = f"/preview/{grant}/index.html"
        return value

    @app.get("/preview/{grant}/{relative:path}")
    def preview(grant: str, relative: str, request: Request):
        capability = app.state.previews.get(grant)
        if not capability or capability["expires"] <= time.time():
            raise HTTPException(404, "Preview expired; refresh the project")
        root = capability["root"]
        path = (root / relative).resolve()
        allowed = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".woff", ".woff2", ".ttf", ".otf"}
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in allowed or any(p.startswith(".") for p in Path(relative).parts):
            raise HTTPException(404, "Preview artifact not found")
        response = FileResponse(path)
        # Opaque sandbox origins cannot carry workspace cookies. A bounded read-only
        # capability serves only generated public artifacts, never APIs or server files.
        origin = str(request.base_url).rstrip("/")
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = f"sandbox allow-scripts; default-src 'none'; script-src {origin}; style-src {origin} 'unsafe-inline'; img-src {origin} data:; font-src {origin}; connect-src 'none'; form-action 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'"
        return response

    @app.post("/api/projects/{project_id}/operations/{operation}", status_code=202)
    def operate(project_id: str, operation: str):
        return engine.queue(project_id, operation)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return engine.store.job(job_id)

    @app.post("/api/projects/{project_id}/review")
    def review(project_id: str, value: Review):
        p = engine.review(project_id, value)
        # Human gate is immediately followed by autonomous production. No fourth gate.
        if value.action == "KEEP" and p["stage"] == "DESIGN_LOCKED":
            engine.queue(project_id, "produce")
        return engine.contextual(p)

    @app.post("/api/projects/{project_id}/visual/regenerate")
    def regenerate(project_id: str):
        return engine.contextual(engine.regenerate(project_id))

    @app.post("/api/projects/{project_id}/final-approval")
    def final(project_id: str, value: FinalApproval):
        if not value.approved:
            raise ValueError("Use a scoped visual revision to request corrections")
        return engine.contextual(engine.final_approve(project_id, value.build_id))

    @app.post("/api/projects/{project_id}/decisions/{decision_id}")
    def resolve(project_id: str, decision_id: str, value: Resolution):
        return engine.contextual(engine.resolve(project_id, decision_id, value.resolution, value.patches))

    @app.post("/api/projects/{project_id}/recovery")
    def recover(project_id: str):
        return engine.recover(project_id)

    @app.post("/api/projects/{project_id}/assets", status_code=201)
    async def upload(project_id: str, file: UploadFile = File(...), role: str = Form("unassigned"), exact: bool = Form(True), restrictions: str = Form("")):
        maximum = int(os.getenv("STUDIO_MAX_UPLOAD_MB", "25")) * 1024 * 1024
        raw = await file.read(maximum + 1)
        await file.close()
        return assets.ingest(engine.store, project_id, file.filename or "upload", raw, role, exact, restrictions)

    @app.patch("/api/projects/{project_id}/assets/{asset_id}")
    def asset_role(project_id: str, asset_id: str, value: AssetRole):
        return assets.assign(engine.store, project_id, asset_id, value.role)

    @app.get("/api/projects/{project_id}/files/{relative:path}")
    def artifact(project_id: str, relative: str, download: bool = False):
        engine.store.get(project_id)
        root = engine.store.path(project_id).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or any(part.startswith(".") for part in Path(relative).parts):
            raise HTTPException(404, "Artifact not found")
        kind = path.suffix.lower()
        # Reference HTML is untrusted evidence and is never executed in Studio origin.
        if relative.startswith(("evidence/", "research/")) and kind in {".html", ".htm"}:
            return Response(path.read_bytes(), media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="source.txt"'})
        if kind in {".py", ".sqlite3", ".db"}:
            raise HTTPException(404, "Private/server artifact is available only inside its tested package")
        response = FileResponse(path, filename=path.name if download else None)
        if kind == ".html":
            # Unique sandbox origin prevents a generated page from reading parent state.
            response.headers["Content-Security-Policy"] = "sandbox allow-scripts allow-forms; default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none'; object-src 'none'; base-uri 'none'"
        return response

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
