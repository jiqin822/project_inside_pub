"""Main FastAPI application."""
import asyncio
import logging
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from app.gcp_credentials import setup_application_default_credentials

# Set Google ADC from inline JSON (e.g. GOOGLE_APPLICATION_CREDENTIALS_JSON on DigitalOcean) before any Google client is used
setup_application_default_credentials()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import time

from app.settings import settings
import os
# Pydantic .env does not set os.environ; sync GCP credential vars from settings so gcp_credentials/STT see them
if getattr(settings, "google_application_credentials", "") and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
if getattr(settings, "google_application_credentials_json", "") and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = settings.google_application_credentials_json
setup_application_default_credentials()
from app.domain.voice.embeddings import ensure_speaker_encoder_loaded
from app.api.admin import router as admin_router
from app.api.coach import router as coach_router
from app.api.interaction import router as interaction_router
from app.api.voice import router as voice_router
from app.api.stt import router as stt_router
from app.api.stt_v2 import router as stt_v2_router
from app.api.market import router as market_router
from app.api.love_map import router as love_map_router
from app.api.notifications import router as notifications_router
from app.api.compass import router as compass_router
from app.api.activity import router as activity_router
from app.api.lounge import router as lounge_router
from app.infra.db.base import Base, engine
# Import all models to ensure they're registered with Base
from app.infra.db.models import (  # noqa: F401
    UserModel,
    RelationshipModel,
    EconomySettingsModel,
    WalletModel,
    MarketItemModel,
    TransactionModel,
    MapPromptModel,
    UserSpecModel,
    RelationshipMapProgressModel,
    NotificationModel,
    DeviceModel,
    CompassEventModel,
    MemoryModel,
    PersonPortraitModel,
    DyadPortraitModel,
    RelationshipLoopModel,
    ActivityTemplateModel,
    DyadActivityHistoryModel,
    ContextSummaryModel,
    LoungeRoomModel,
    LoungeMemberModel,
    LoungeMessageModel,
    LoungeKaiContextModel,
    LoungeEventModel,
    LoungeKaiUserPreferenceModel,
)
from app.infra.messaging.redis_bus import redis_bus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # Log error but don't fail startup - database might not be ready yet
        print(f"Warning: Could not connect to database during startup: {e}")
        print("Make sure PostgreSQL is running and accessible.")

    # Connect Redis and start lounge room-updates subscriber (so WebSocket updates reach all instances)
    lounge_subscriber_task = None
    try:
        await redis_bus.connect()
        from app.infra.realtime.lounge_ws_manager import lounge_ws_manager, LOUNGE_ROOM_UPDATES_CHANNEL

        async def _lounge_room_updates_handler(data: dict) -> None:
            await lounge_ws_manager.broadcast_local(data["room_id"], data["message"])

        lounge_subscriber_task = asyncio.create_task(
            redis_bus.subscribe_forever(LOUNGE_ROOM_UPDATES_CHANNEL, _lounge_room_updates_handler)
        )
        logger.info("Lounge room updates Redis subscriber started")
    except Exception as e:
        print(f"Warning: Could not connect to Redis during startup: {e}")
        print("Make sure Redis is running and accessible.")

    # Load speaker encoder (ECAPA-TDNN) so speaker embeddings are available (runs in thread to avoid blocking)
    try:
        ok, msg = await asyncio.to_thread(ensure_speaker_encoder_loaded)
        if ok:
            logger.info("Speaker encoder: %s", msg)
        else:
            logger.warning(
                "Speaker encoder: %s (Python: %s). For speaker IDs use: pip install speechbrain",
                msg,
                sys.executable,
            )
    except Exception as e:
        logger.warning("Speaker encoder startup check failed: %s", e)

    # Check google.genai (activity LLM); log clearly if missing so user knows to poetry install
    try:
        import google.genai as _  # noqa: F401
        logger.info("google.genai available (activity recommendations LLM enabled)")
    except (ImportError, ModuleNotFoundError) as e:
        logger.error(
            "google.genai could not be imported: %s. Activity recommendations will use seed fallback. "
            "From backend dir run: poetry install (or pip install google-genai), then restart the server.",
            e,
        )

    # NeMo diarization (STT): check availability once at startup; store for STT route
    try:
        from app.domain.stt.nemo_sortformer_diarizer import nemo_diarization_available
        ok, err = await asyncio.to_thread(nemo_diarization_available)
        app.state.nemo_diarization_available = ok
        app.state.nemo_diarization_error = err
        if ok:
            logger.info("NeMo diarization available (STT speaker labels)")
        else:
            logger.warning(
                "NeMo diarization unavailable: %s. Set STT_ENABLE_NEMO_DIARIZATION_FALLBACK=false to silence.",
                err,
            )
    except Exception as e:
        logger.warning("NeMo diarization startup check failed: %s", e)
        app.state.nemo_diarization_available = False
        app.state.nemo_diarization_error = str(e)

    # Load Kai prompts (base + lounge) at startup
    try:
        from app.domain.kai.agent import _get_base_prompt, _get_lounge_prompt, _get_intervention_prompt, _get_single_user_prompt
        _get_base_prompt()
        _get_lounge_prompt()
        _get_intervention_prompt()
        _get_single_user_prompt()
    except Exception as e:
        logger.warning("Kai prompt load at startup failed: %s", e)

    yield

    # Shutdown (CancelledError here or in Starlette's receive() is normal on Ctrl+C)
    try:
        if lounge_subscriber_task is not None:
            lounge_subscriber_task.cancel()
            try:
                await lounge_subscriber_task
            except asyncio.CancelledError:
                pass
        await redis_bus.disconnect()
        await engine.dispose()
    except asyncio.CancelledError:
        logger.info("Lifespan shutdown cancelled (e.g. Ctrl+C); cleanup attempted.")
        raise


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS: allow any request origin (reflect request Origin in Access-Control-Allow-Origin).
# allow_origin_regex=".*" accepts every origin; credentials still work.
logger.info("🔧 CORS: allow any origin (reflect request Origin)")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"📥 [SERVER REQUEST] {request.method} {request.url.path}")
        
        # For OPTIONS requests, log origin for debugging CORS
        if request.method == "OPTIONS":
            origin = request.headers.get("origin", "no-origin")
            logger.info(f"   CORS Origin: {origin}")
            logger.info(f"   Access-Control-Request-Method: {request.headers.get('access-control-request-method', 'N/A')}")
            logger.info(f"   Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'N/A')}")
        
        logger.debug(f"   Query params: {dict(request.query_params)}")
        if request.headers:
            # Don't log authorization header fully
            headers = dict(request.headers)
            if 'authorization' in headers:
                auth_header = headers['authorization']
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                    headers['authorization'] = f'Bearer {token[:20]}...' if len(token) > 20 else 'Bearer ***'
            logger.debug(f"   Headers: {headers}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(f"📤 [SERVER RESPONSE] {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
        
        # For OPTIONS, log CORS headers in response
        if request.method == "OPTIONS":
            cors_headers = {k: v for k, v in response.headers.items() if k.lower().startswith('access-control')}
            if cors_headers:
                logger.info(f"   CORS Response Headers: {cors_headers}")
            else:
                logger.warning(f"   ⚠️  No CORS headers in OPTIONS response!")
        
        return response


# Add logging middleware AFTER CORS (CORS must be first)
app.add_middleware(LoggingMiddleware)

# Add validation error handler for better error logging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging."""
    import json
    logger.error(f"❌ [VALIDATION ERROR] {request.method} {request.url.path}")
    
    # Try to get body from exception (FastAPI stores it there)
    if hasattr(exc, 'body') and exc.body:
        try:
            body_str = exc.body.decode('utf-8') if isinstance(exc.body, bytes) else str(exc.body)
            logger.error(f"   Request body: {body_str}")
        except Exception as e:
            logger.error(f"   Could not decode request body: {e}")
    else:
        # Fallback: try to read from request
        try:
            body = await request.body()
            logger.error(f"   Request body (from request): {body.decode('utf-8') if body else 'empty'}")
        except Exception as e:
            logger.error(f"   Could not read request body: {e}")
    
    # Log validation errors in a readable format
    errors = exc.errors()
    logger.error(f"   Validation errors ({len(errors)}):")
    for i, error in enumerate(errors, 1):
        error_msg = json.dumps(error, indent=2)
        logger.error(f"   Error {i}: {error_msg}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": errors}
    )


# Domain error handlers: map domain exceptions to correct HTTP status
from app.domain.common.errors import (
    NotFoundError as DomainNotFoundError,
    AuthorizationError as DomainAuthorizationError,
    ValidationError as DomainValidationError,
    ConflictError as DomainConflictError,
)


@app.exception_handler(DomainNotFoundError)
async def domain_not_found_handler(request: Request, exc: DomainNotFoundError):
    """Return 404 when a resource is not found."""
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(DomainAuthorizationError)
async def domain_authorization_handler(request: Request, exc: DomainAuthorizationError):
    """Return 403 when the user is not authorized."""
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message if hasattr(exc, "message") else str(exc)},
    )


@app.exception_handler(DomainValidationError)
async def domain_validation_handler(request: Request, exc: DomainValidationError):
    """Return 422 for domain validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message if hasattr(exc, "message") else str(exc)},
    )


@app.exception_handler(DomainConflictError)
async def domain_conflict_handler(request: Request, exc: DomainConflictError):
    """Return 409 for conflict errors."""
    return JSONResponse(
        status_code=409,
        content={"detail": exc.message if hasattr(exc, "message") else str(exc)},
    )


# Health check (root and under /v1 so GET /v1/health works when Nginx proxies with /v1 prefix)
@app.get("/health")
@app.get(f"{settings.api_v1_prefix}/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


# Readiness: config, packages, DB, Redis, optional voiceprint
@app.get("/ready")
async def readiness():
    """Readiness endpoint: run all checks and return 200 if ready, 503 otherwise."""
    from app.readiness import run_all_checks_async, is_ready
    checks = await run_all_checks_async()
    ready, summary = is_ready(checks)
    if ready:
        return {"ready": True, "checks": summary}
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=503,
        content={"ready": False, "checks": summary},
    )


# Serve uploaded activity memory images (GET /storage/activity_memories/...)
# Must be registered before the catch-all OPTIONS so GET requests are served here
_storage_dir = Path(__file__).resolve().parent.parent / "storage"
_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(_storage_dir)), name="storage")


# Redirect GET /signup?token=... to the app's signup page (in case invite link hits API instead of frontend).
@app.get("/signup")
async def signup_redirect(token: str | None = None):
    """If the API receives GET /signup (e.g. invite link misrouted), redirect to the frontend signup page."""
    from urllib.parse import quote
    from fastapi.responses import RedirectResponse
    base = (settings.app_public_url or "").rstrip("/") or "http://localhost:3000"
    url = f"{base}/signup"
    if token:
        url += f"?token={quote(token)}"
    return RedirectResponse(url=url, status_code=302)


# Explicit OPTIONS handler for CORS preflight: allow any origin (reflect request Origin).
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle OPTIONS preflight; allow any origin."""
    from fastapi.responses import Response
    origin = (request.headers.get("origin") or "").strip() or "*"
    # With credentials, browser requires a specific origin; use request origin when present.
    allow_origin = origin if origin != "*" else "*"
    logger.info(f"🔧 OPTIONS {full_path!r} origin={origin!r} -> Allow-Origin={allow_origin!r}")
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        },
    )


# API v1 routes
app.include_router(admin_router, prefix=settings.api_v1_prefix, tags=["admin"])
app.include_router(coach_router, prefix=f"{settings.api_v1_prefix}/coach", tags=["coach"])
app.include_router(interaction_router, prefix=settings.api_v1_prefix, tags=["interaction"])
app.include_router(voice_router, prefix=settings.api_v1_prefix, tags=["voice"])
app.include_router(stt_router, prefix=settings.api_v1_prefix, tags=["stt"])
app.include_router(market_router, prefix=settings.api_v1_prefix, tags=["market"])
app.include_router(love_map_router, prefix=f"{settings.api_v1_prefix}/love-map", tags=["love-map"])
app.include_router(notifications_router, prefix=settings.api_v1_prefix, tags=["notifications"])
app.include_router(compass_router, prefix=f"{settings.api_v1_prefix}/compass", tags=["compass"])
app.include_router(activity_router, prefix=f"{settings.api_v1_prefix}/activity", tags=["activity"])
app.include_router(lounge_router, prefix=f"{settings.api_v1_prefix}/lounge", tags=["lounge"])
app.include_router(stt_v2_router, prefix=settings.api_v1_prefix, tags=["stt-v2"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
