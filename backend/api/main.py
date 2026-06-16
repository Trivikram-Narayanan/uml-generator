"""api/main.py  –  Production FastAPI app v3"""
from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from db.database import init_db
from api.routers.auth       import router as auth_router
from api.routers.diagrams   import router as diagrams_router
from api.routers.feedback   import router as feedback_router
from api.routers.versions   import router as versions_router
from api.routers.tags       import router as tags_router
from api.routers.workspaces import router as workspaces_router
from api.routers.templates  import router as templates_router
from api.routers.search     import router as search_router

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_log_level,
    structlog.dev.ConsoleRenderer(),
])
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting UMLGen API v3…")
    await init_db()
    await _seed_anon_user()
    await _seed_templates()
    logger.info("Ready")
    yield

app = FastAPI(title="UMLGen API", version="3.0.0", lifespan=lifespan,
              docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS","*").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter()-start)*1000, 1)
    logger.info("req", method=request.method, path=request.url.path,
                status=response.status_code, ms=ms)
    return response

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.error("unhandled", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail":"Internal server error."})

for r in [auth_router, diagrams_router, feedback_router, versions_router,
          tags_router, workspaces_router, templates_router, search_router]:
    app.include_router(r)

@app.get("/api/health",         tags=["system"]) 
def health(): return {"status":"ok","version":"3.0.0"}

@app.get("/api/diagram-types",  tags=["system"])
def diagram_types(): return {"types":["sequence","class","usecase","activity","component","state","er"]}

@app.get("/api/languages",      tags=["system"])
def languages():
    from llm.code_generator import SUPPORTED_LANGUAGES
    return {"languages": SUPPORTED_LANGUAGES}

@app.get("/api/models",         tags=["system"])
def models():
    import os
    return {
        "backend": os.getenv("LLM_BACKEND","ollama"),
        "active_model": os.getenv("OLLAMA_MODEL","codellama:7b-code"),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY","")),
        "gemini_model": os.getenv("GEMINI_MODEL","gemini-2.0-flash"),
        "supported_gemini_models": ["gemini-2.0-flash","gemini-1.5-pro","gemini-1.5-flash"],
    }


async def _seed_anon_user():
    """Create the anonymous user used when REQUIRE_AUTH=false."""
    if os.getenv("REQUIRE_AUTH", "false").lower() == "true":
        return
    from db.database import AsyncSessionLocal
    from db.models import User
    from sqlalchemy import select
    from auth.security import ANON_USER_ID
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(User).where(User.id == ANON_USER_ID))
        if not r.scalar_one_or_none():
            session.add(User(
                id=ANON_USER_ID,
                email="anon@localhost",
                username="anon",
                password_hash="!",  # not a valid bcrypt hash — cannot login
                is_active=True,
            ))
        await session.commit()


async def _seed_templates():
    """Insert built-in templates if they don't exist yet."""
    from db.database import AsyncSessionLocal
    from db.models import Template
    from sqlalchemy import select
    TEMPLATES = [
        {"title":"User Login (JWT)","description":"User login with JWT tokens and refresh rotation","diagram_type":"sequence","category":"Auth","plantuml_code":"@startuml\nactor User\nparticipant Browser\nparticipant AuthServer\nparticipant Database\nUser -> Browser: enter credentials\nBrowser -> AuthServer: POST /auth/login\nAuthServer -> Database: SELECT user\nDatabase --> AuthServer: user record\nAuthServer -> AuthServer: verify hash\nalt valid\n  AuthServer --> Browser: 200 + JWT\nelse invalid\n  AuthServer --> Browser: 401\nend\n@enduml"},
        {"title":"E-Commerce Domain","description":"E-commerce system with products, orders, and customers","diagram_type":"class","category":"E-Commerce","plantuml_code":"@startuml\nclass Customer {\n  +id: UUID\n  +email: String\n  +placeOrder(): Order\n}\nclass Order {\n  +id: UUID\n  +total: Decimal\n  +status: String\n}\nclass Product {\n  +name: String\n  +price: Decimal\n  +stock: Integer\n}\nclass OrderItem {\n  +quantity: Integer\n  +unitPrice: Decimal\n}\nCustomer --> Order : places\nOrder *-- OrderItem\nOrderItem --> Product\n@enduml"},
        {"title":"Microservices Architecture","description":"Microservices with API gateway and message queue","diagram_type":"component","category":"Architecture","plantuml_code":"@startuml\npackage \"Client\" {\n  [Web App]\n  [Mobile App]\n}\npackage \"Gateway\" {\n  [API Gateway]\n}\npackage \"Services\" {\n  [User Service]\n  [Order Service]\n  [Notification Service]\n}\ndatabase \"DB\" as DB\nqueue \"Message Queue\" as MQ\n[Web App] --> [API Gateway]\n[Mobile App] --> [API Gateway]\n[API Gateway] --> [User Service]\n[API Gateway] --> [Order Service]\n[Order Service] --> MQ\nMQ --> [Notification Service]\n[User Service] --> DB\n[Order Service] --> DB\n@enduml"},
        {"title":"Order State Machine","description":"Order lifecycle states from pending to delivered","diagram_type":"state","category":"E-Commerce","plantuml_code":"@startuml\n[*] --> Pending\nPending --> Confirmed : payment received\nPending --> Cancelled : user cancels\nConfirmed --> Processing : warehouse picks\nProcessing --> Shipped : carrier collects\nShipped --> Delivered : delivered\nShipped --> Returned : refused\nDelivered --> Returned : return request\nCancelled --> [*]\nDelivered --> [*]\nReturned --> [*]\n@enduml"},
        {"title":"Checkout Flow","description":"E-commerce checkout with payment handling","diagram_type":"activity","category":"E-Commerce","plantuml_code":"@startuml\nstart\n:View cart;\nif (Cart empty?) then (yes)\n  :Show empty message;\n  stop\nelse (no)\n  :Enter shipping details;\n  :Enter payment;\n  if (Payment valid?) then (yes)\n    :Process payment;\n    :Create order;\n    :Send confirmation email;\n    stop\n  else (no)\n    :Show error;\n    :Return to payment;\n  endif\nendif\n@enduml"},
        {"title":"Blog Schema","description":"Blog platform ER diagram with users, posts, comments, tags","diagram_type":"er","category":"Database","plantuml_code":"@startuml\nentity User {\n  * id : UUID <<PK>>\n  --\n  * username : VARCHAR(50)\n  * email : VARCHAR(255)\n}\nentity Post {\n  * id : UUID <<PK>>\n  --\n  * title : VARCHAR(255)\n  * content : TEXT\n  * userId : UUID <<FK>>\n}\nentity Comment {\n  * id : UUID <<PK>>\n  --\n  * body : TEXT\n  * userId : UUID <<FK>>\n  * postId : UUID <<FK>>\n}\nUser ||--o{ Post : writes\nUser ||--o{ Comment : makes\nPost ||--o{ Comment : has\n@enduml"},
    ]
    async with AsyncSessionLocal() as session:
        for t in TEMPLATES:
            r = await session.execute(select(Template).where(
                Template.title==t["title"], Template.is_builtin==True))
            if not r.scalar_one_or_none():
                session.add(Template(**t, is_builtin=True))
        await session.commit()


# ── Security headers middleware ───────────────────────────────────────────────
# Applied to every response. Reduces XSS / clickjacking surface.

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]          = "DENY"
    response.headers["X-XSS-Protection"]         = "1; mode=block"
    response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
    return response
