import asyncio
from contextlib import asynccontextmanager
import hmac
from pathlib import Path
import time

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import AccessSession, Sessions, verify_password
from .capture import CameraPipeline
from .inference import Mode
from .runtime import LiveRuntime
from .settings import Settings

COOKIE = "tecnosolda_access"


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class SimulationControl(BaseModel):
    removed: bool
    mode: Mode


class AccessBoundary:
    """ASGI: aplica rede/origem também ao WebSocket; ignora X-Forwarded-For."""

    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode().lower()
        origin = headers.get(b"origin", b"").decode()
        client = scope.get("client")
        allowed = bool(client and self.settings.allows(client[0]) and host == self.settings.host.lower())
        if origin and origin != self.settings.origin:
            allowed = False
        if scope["type"] == "websocket" and origin != self.settings.origin:
            allowed = False
        if headers.get(b"sec-fetch-site") == b"cross-site":
            allowed = False
        if not allowed:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse({"detail": "Acesso fora da origem/rede autorizada."},
                                      status_code=403)(scope, receive, send)
        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store, private, max-age=0"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"permissions-policy", b"camera=(), microphone=()"),
                    (b"content-security-policy",
                     b"default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
                     b"script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"),
                ]
            await send(message)
        await self.app(scope, receive, secured_send)


async def mjpeg_frames(runtime: LiveRuntime, sessions: Sessions, token: str):
    last_sequence = -1
    while sessions.get(token):
        packet, _ = runtime.pipeline.latest()
        if (packet and packet.version == runtime.version and packet.sequence != last_sequence
                and 0 <= time.monotonic() - packet.captured_at <= runtime.pipeline.settings.frame_timeout):
            last_sequence = packet.sequence
            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                   str(len(packet.jpeg)).encode() + b"\r\n\r\n" + packet.jpeg + b"\r\n")
        await asyncio.sleep(0.05)


class SessionStream(StreamingResponse):
    """Fecha também uma escrita bloqueada quando expira/revoga o acesso."""

    def __init__(self, content, sessions: Sessions, token: str):
        super().__init__(content, media_type="multipart/x-mixed-replace; boundary=frame",
                         headers={"X-Accel-Buffering": "no"})
        self.sessions, self.token = sessions, token

    async def __call__(self, scope, receive, send):
        async def expiry():
            while self.sessions.get(self.token):
                await asyncio.sleep(0.1)
        stream = asyncio.create_task(super().__call__(scope, receive, send))
        timer = asyncio.create_task(expiry())
        try:
            done, _ = await asyncio.wait({stream, timer}, return_when=asyncio.FIRST_COMPLETED)
            if stream in done:
                await stream
            else:
                stream.cancel()
                await asyncio.gather(stream, return_exceptions=True)
                try:
                    await asyncio.wait_for(send({"type": "http.response.body", "body": b"",
                                                 "more_body": False}), timeout=0.2)
                except (TimeoutError, OSError, RuntimeError):
                    pass
        finally:
            stream.cancel()
            timer.cancel()
            await asyncio.gather(stream, timer, return_exceptions=True)
            if hasattr(self.body_iterator, "aclose"):
                await self.body_iterator.aclose()


def create_app(settings: Settings | None = None, runtime: LiveRuntime | None = None,
               sessions: Sessions | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runtime = runtime or LiveRuntime(CameraPipeline(settings))
    sessions = sessions or Sessions(settings.session_seconds)

    @asynccontextmanager
    async def lifespan(app):
        runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="TecnoSolda LAN", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(AccessBoundary, settings=settings)
    app.state.runtime, app.state.sessions = runtime, sessions
    connections: dict[str, int] = {}

    def reserve(token: str) -> None:
        if sum(connections.values()) >= 16 or connections.get(token, 0) >= 4:
            raise HTTPException(429, "Limite de transmissões simultâneas atingido.")
        connections[token] = connections.get(token, 0) + 1

    def release(token: str) -> None:
        connections[token] = max(0, connections.get(token, 0) - 1)
        if not connections[token]:
            del connections[token]

    def access(request: Request, mutate: bool = False) -> AccessSession:
        session = sessions.get(request.cookies.get(COOKIE))
        if not session:
            raise HTTPException(401, "Sessão expirada ou acesso não autenticado.")
        if mutate and (request.headers.get("origin") != settings.origin or
                       not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf)):
            raise HTTPException(403, "Origem ou token CSRF inválido.")
        return session

    def public_session(session: AccessSession) -> dict:
        return {"username": session.username, "role": session.role, "csrf": session.csrf,
                "expires_in": max(0, session.expires_at - sessions.clock())}

    @app.post("/api/auth/login")
    async def login(body: Login, request: Request, response: Response):
        if request.headers.get("origin") != settings.origin:
            raise HTTPException(403, "Origem inválida.")
        if not sessions.permit_attempt(request.client.host):
            raise HTTPException(429, "Muitas tentativas. Aguarde um minuto.")
        valid_password = await asyncio.to_thread(verify_password, body.password, settings.password_hash)
        if not valid_password or not hmac.compare_digest(body.username.encode(), settings.username.encode()):
            runtime.audit("ACESSO_NEGADO", "credenciais_invalidas")
            raise HTTPException(401, "Credenciais inválidas.")
        sessions.revoke(request.cookies.get(COOKIE))
        token, session = sessions.issue(settings.username)
        response.set_cookie(COOKIE, token, max_age=settings.session_seconds,
                            httponly=True, secure=settings.secure_cookie,
                            samesite="strict", path="/api")
        runtime.audit("ACESSO_INICIADO", "operador_autenticado", session.username)
        return public_session(session)

    @app.get("/api/auth/session")
    async def current_session(request: Request):
        return public_session(access(request))

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        session = access(request, mutate=True)
        sessions.revoke(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/api", secure=settings.secure_cookie,
                               httponly=True, samesite="strict")
        runtime.audit("ACESSO_ENCERRADO", "logout", session.username)
        return {"ok": True}

    @app.get("/api/live/status")
    async def status(request: Request):
        access(request)
        return runtime.data

    @app.get("/api/alerts")
    async def alerts(request: Request):
        access(request)
        return {"events": runtime.controller.engine.events.as_dicts()}

    @app.post("/api/simulation")
    async def simulation(body: SimulationControl, request: Request):
        session = access(request, mutate=True)
        runtime.configure(body.removed, body.mode, session.username)
        return {"ok": True, "simulated": True}

    @app.post("/api/alerts/acknowledge")
    async def acknowledge(request: Request):
        session = access(request, mutate=True)
        try:
            runtime.acknowledge(session.username)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {"ok": True}

    @app.get("/api/live/video.mjpg")
    async def video(request: Request):
        access(request)
        token = request.cookies[COOKIE]
        reserve(token)
        runtime.audit("VIDEO_ABERTO", "mjpeg_autenticado", sessions.get(token).username)
        async def stream():
            try:
                async for part in mjpeg_frames(runtime, sessions, token):
                    yield part
            finally:
                release(token)
        return SessionStream(stream(), sessions, token)

    @app.websocket("/api/live/ws")
    async def websocket(socket: WebSocket):
        token = socket.cookies.get(COOKIE, "")
        if not sessions.get(token):
            await socket.close(code=4401)
            return
        try:
            reserve(token)
        except HTTPException:
            await socket.close(code=4429)
            return
        await socket.accept()
        try:
            while sessions.get(token):
                session = sessions.get(token)
                await asyncio.wait_for(socket.send_json({
                    **runtime.data,
                    "access_expires_in": max(0, session.expires_at - sessions.clock()),
                }), timeout=1)
                try:
                    message = await asyncio.wait_for(socket.receive(), timeout=0.2)
                    if message["type"] == "websocket.disconnect":
                        return
                except TimeoutError:
                    pass
            await socket.close(code=4401, reason="Sessão expirada.")
        except (WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
            pass
        finally:
            release(token)

    frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="dashboard")
    return app
