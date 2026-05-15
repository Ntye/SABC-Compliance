from __future__ import annotations
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core.errors import (
    ConflictError, DomainError, ExternalServiceError, ForbiddenError,
    NotFoundError, SSHConnectError, UnauthorizedError, ValidationError,
)
from infrastructure.database.adapter import (
    ApiKeyRepository, AuditRepository, ComplianceRepository,
    JobRepository, NodeRepository, RuleRepository, UserRepository,
    create_db,
)
from modules.auth.usecases import (
    AuthenticateUseCase, ChangePasswordUseCase, CreateApiKeyUseCase,
    CreateUserUseCase, DecodeJwtUseCase, InitAdminUserUseCase,
    InitApiKeyUseCase, ListApiKeysUseCase, ListUsersUseCase, LoginUseCase,
    RevokeApiKeyUseCase,
)
from core.events import EventBus
from infrastructure.ssh.adapter import SshClientAdapter
from modules.nodes.usecases import (
    CheckNodeDnsUseCase, DeleteNodeUseCase, GetNodeUseCase, ListNodesUseCase,
    PingAllNodesUseCase, PingNodeUseCase, RegisterNodeUseCase, UpdateNodeUseCase,
)
from interface.http.routes import auth as auth_routes
from interface.http.routes import nodes as nodes_routes
from interface.http.middleware import AuditMiddleware, RateLimitMiddleware
from interface.websocket.manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║          BdC Compliance Platform  v1.0.0             ║
║          Boissons du Cameroun                        ║
╠══════════════════════════════════════════════════════╣
║  API:     http://0.0.0.0:{port:<5}                      ║
║  Docs:    http://localhost:{port:<5}/docs                ║
║  ReDoc:   http://localhost:{port:<5}/redoc               ║
╚══════════════════════════════════════════════════════╝
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # -- Database --
    os.makedirs(os.path.dirname(settings.db_path) if os.path.dirname(settings.db_path) else "data", exist_ok=True)
    engine, session_factory = await create_db(settings.db_path)

    # -- Repositories --
    node_repo = NodeRepository(session_factory)
    job_repo = JobRepository(session_factory)
    compliance_repo = ComplianceRepository(session_factory)
    api_key_repo = ApiKeyRepository(session_factory)
    user_repo = UserRepository(session_factory)
    audit_repo = AuditRepository(session_factory)
    rule_repo = RuleRepository(session_factory)

    # -- Event bus --
    event_bus = EventBus()

    # -- Auth use cases --
    authenticate_uc = AuthenticateUseCase(api_key_repo)
    decode_jwt_uc = DecodeJwtUseCase(settings.jwt_secret, settings.jwt_algorithm, user_repo)
    init_api_key_uc = InitApiKeyUseCase(api_key_repo)
    create_api_key_uc = CreateApiKeyUseCase(api_key_repo)
    list_api_keys_uc = ListApiKeysUseCase(api_key_repo)
    revoke_api_key_uc = RevokeApiKeyUseCase(api_key_repo)
    login_uc = LoginUseCase(user_repo, settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expire_hours)
    init_admin_user_uc = InitAdminUserUseCase(user_repo)
    create_user_uc = CreateUserUseCase(user_repo)
    list_users_uc = ListUsersUseCase(user_repo)
    change_password_uc = ChangePasswordUseCase(user_repo)

    # -- Wire auth routes --
    auth_routes.set_use_cases(
        authenticate_uc=authenticate_uc,
        decode_jwt_uc=decode_jwt_uc,
        init_api_key_uc=init_api_key_uc,
        create_api_key_uc=create_api_key_uc,
        list_api_keys_uc=list_api_keys_uc,
        revoke_api_key_uc=revoke_api_key_uc,
        login_uc=login_uc,
        create_user_uc=create_user_uc,
        list_users_uc=list_users_uc,
        change_password_uc=change_password_uc,
    )

    # -- WebSocket manager (stub) --
    ws_manager = WebSocketManager(job_repo)

    # -- SSH client --
    ssh_client = SshClientAdapter(settings.ssh_key_path)

    # -- Node use cases --
    register_node_uc = RegisterNodeUseCase(node_repo, ssh_client, event_bus)
    get_node_uc = GetNodeUseCase(node_repo)
    list_nodes_uc = ListNodesUseCase(node_repo)
    ping_node_uc = PingNodeUseCase(node_repo, ssh_client)
    ping_all_uc = PingAllNodesUseCase(node_repo, ssh_client)
    update_node_uc = UpdateNodeUseCase(node_repo)
    delete_node_uc = DeleteNodeUseCase(node_repo)
    check_dns_uc = CheckNodeDnsUseCase(
        node_repo, ssh_client,
        settings.puppet_master_host,
        settings.wazuh_manager_host,
    )

    nodes_routes.set_use_cases(
        register_uc=register_node_uc,
        get_uc=get_node_uc,
        list_uc=list_nodes_uc,
        ping_uc=ping_node_uc,
        ping_all_uc=ping_all_uc,
        update_uc=update_node_uc,
        delete_uc=delete_node_uc,
        check_dns_uc=check_dns_uc,
    )

    # -- Attach audit repo to middleware --
    app.state.audit_repo = audit_repo

    # -- Bootstrap admin user --
    try:
        user_creds = await init_admin_user_uc.execute()
        if user_creds:
            print("\n" + "=" * 60)
            print("  FIRST-RUN: Admin user created")
            print(f"  Username : {user_creds['username']}")
            print(f"  Password : {user_creds['password']}")
            print("  Store these credentials securely!")
            print("=" * 60 + "\n", flush=True)
    except Exception as exc:
        logger.debug("Admin user bootstrap: %s", exc)

    # -- Bootstrap admin API key --
    try:
        key_result = await init_api_key_uc.execute()
        if key_result:
            print("\n" + "=" * 60)
            print("  FIRST-RUN: Admin API key created")
            print(f"  API Key: {key_result['api_key']}")
            print("  Store this key securely — it will not be shown again!")
            print("=" * 60 + "\n", flush=True)
    except ConflictError:
        pass

    print(_BANNER.format(port=settings.port), flush=True)

    yield

    # -- Shutdown --
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BdC Compliance Platform API",
        version="1.0.0",
        description="""
## BdC Integrated Linux Compliance Platform

Manages a fleet of Linux servers (Rocky Linux 9 + Ubuntu 22.04) with automated
compliance enforcement across **CIS Benchmarks**, **ISO/IEC 27001**, and **PCI-DSS**.

### Closed Feedback Loop
Wazuh detects a violation → webhook → Puppet remediation → recorded result.

### Authentication
Two methods accepted on all protected endpoints:
- `X-API-Key: bdc_...` — machine-to-machine API key
- `Authorization: Bearer <jwt>` — user session token (from POST /auth/login)

### Stub Mode
When `PUPPET_MASTER_HOST` / `WAZUH_MANAGER_HOST` are not set, all external calls
return safe empty responses. Every endpoint works in stub mode.
        """,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health", "description": "Platform health checks"},
            {"name": "Auth", "description": "Authentication — API keys and user login"},
            {"name": "Nodes", "description": "Linux server node registry"},
            {"name": "Jobs", "description": "Ansible provisioning jobs"},
            {"name": "Compliance", "description": "Compliance reports and remediation"},
            {"name": "Rules", "description": "Puppet compliance rules library"},
            {"name": "Audit", "description": "HTTP audit log"},
            {"name": "Webhooks", "description": "Internal webhook endpoints"},
        ],
    )

    settings_obj = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings_obj.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_per_minute=200)
    # AuditMiddleware reads audit_repo from request.app.state (set in lifespan)
    app.add_middleware(AuditMiddleware)

    # Register error handlers
    error_map = {
        NotFoundError: 404,
        ConflictError: 409,
        ValidationError: 422,
        UnauthorizedError: 401,
        ForbiddenError: 403,
        SSHConnectError: 422,
        ExternalServiceError: 502,
    }
    for exc_class, status_code in error_map.items():
        @app.exception_handler(exc_class)
        async def _handler(request, exc, sc=status_code):
            return JSONResponse({"error": str(exc), "code": exc.code}, status_code=sc)

    # Include routers
    app.include_router(auth_routes.router)
    app.include_router(nodes_routes.router)

    # Health stub (minimal — full implementation in Feature 6)
    from fastapi import APIRouter
    health_router = APIRouter(tags=["Health"])

    @health_router.get("/health", summary="Platform health check")
    async def health():
        """Returns health status for all platform services."""
        return {
            "status": "up",
            "services": {
                "api": {"status": "up"},
                "puppet": {"status": "not_configured"},
                "wazuh": {"status": "not_configured"},
                "ansible": {"status": "unknown"},
            }
        }

    app.include_router(health_router)

    return app


app = create_app()
