from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core.errors import (
    ConflictError, ExternalServiceError, ForbiddenError,
    NotFoundError, SSHConnectError, UnauthorizedError, ValidationError,
)
from infrastructure.database.adapter import (
    ApiKeyRepository, AuditRepository, ComplianceRepository,
    JobRepository, NodeRepository, NodeGroupRepository, PlatformConfigRepository,
    RuleRepository, UserRepository, UserGroupRepository, create_db,
)
from infrastructure.http.wazuh_client import WazuhRESTClient
from infrastructure.http.puppet_nc_client import PuppetNCClient
from modules.auth.usecases import (
    AuthenticateUseCase, ChangePasswordUseCase, CreateApiKeyUseCase,
    CreateUserUseCase, DecodeJwtUseCase, InitAdminUserUseCase,
    InitApiKeyUseCase, ListApiKeysUseCase, ListUsersUseCase, LoginUseCase,
    RevokeApiKeyUseCase, UpdateUserUseCase, DeleteUserUseCase,
    CreateUserGroupUseCase, ListUserGroupsUseCase, GetUserGroupUseCase,
    UpdateUserGroupUseCase, DeleteUserGroupUseCase,
    AddUserToGroupUseCase, RemoveUserFromGroupUseCase,
    SeedDefaultGroupsUseCase,
)
from modules.node_groups.usecases import (
    CreateNodeGroupUseCase, DeleteNodeGroupUseCase, ListNodeGroupsUseCase,
    GetNodeGroupUseCase, AddNodeToGroupUseCase, RemoveNodeFromGroupUseCase,
)
from core.events import EventBus
from infrastructure.ssh.adapter import SshClientAdapter
from infrastructure.ansible.adapter import AnsibleAdapter
from modules.nodes.usecases import (
    ChangeNodeIdentityUseCase, CheckNodeDnsUseCase, DeleteNodeUseCase,
    FixNodeDnsUseCase, GetNodeUseCase, ListNodesUseCase,
    PingAllNodesUseCase, PingNodeUseCase, RegisterNodeUseCase, UpdateNodeUseCase,
)
from modules.provisioning.usecases import (
    CancelJobUseCase, DetectAgentsUseCase, GetInfrastructureStatusUseCase,
    GetJobUseCase, InspecControllerUseCase, InstallServiceUseCase, ListJobsUseCase,
    SetMasterHostUseCase, StartJobUseCase,
)
from modules.compliance.usecases import (
    CollectNodeComplianceUseCase, GetComplianceSummaryUseCase,
    GetNodeComplianceUseCase, TriggerRemediationUseCase,
)
from interface.http.routes import auth as auth_routes
from interface.http.routes import nodes as nodes_routes
from interface.http.routes import infrastructure as infrastructure_routes
from interface.http.routes import jobs as jobs_routes
from interface.http.routes import compliance as compliance_routes
from interface.http.routes import node_groups as node_groups_routes
from interface.http.middleware import AuditMiddleware, RateLimitMiddleware
from interface.websocket.manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║          SABC Compliance Platform  v1.0.0            ║
║          Société Anonyme des Brasseries du Cameroun  ║
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
    platform_config_repo = PlatformConfigRepository(session_factory)
    group_repo = UserGroupRepository(session_factory)
    node_group_repo = NodeGroupRepository(session_factory)

    # -- External service clients --
    wazuh_client = WazuhRESTClient(
        host=settings.wazuh_manager_host,
        port=settings.wazuh_api_port,
        user=settings.wazuh_api_user,
        password=settings.wazuh_api_pass,
        token_refresh_seconds=settings.wazuh_token_refresh_seconds,
    )
    puppet_nc_client = PuppetNCClient(
        host=settings.puppet_master_host,
        rbac_port=settings.puppet_rbac_port,
        admin_user=settings.puppet_admin_user,
        admin_pass=settings.puppet_admin_pass,
        token_rotate_seconds=settings.puppet_token_rotate_seconds,
    )

    # -- Event bus --
    event_bus = EventBus()

    # -- Auth use cases --
    authenticate_uc = AuthenticateUseCase(api_key_repo)
    decode_jwt_uc = DecodeJwtUseCase(settings.jwt_secret, settings.jwt_algorithm, user_repo)
    init_api_key_uc = InitApiKeyUseCase(api_key_repo)
    create_api_key_uc = CreateApiKeyUseCase(api_key_repo)
    list_api_keys_uc = ListApiKeysUseCase(api_key_repo)
    revoke_api_key_uc = RevokeApiKeyUseCase(api_key_repo)
    login_uc = LoginUseCase(
        user_repo, api_key_repo, group_repo,
        settings.jwt_secret, settings.jwt_algorithm, settings.jwt_expire_hours,
    )
    init_admin_user_uc = InitAdminUserUseCase(user_repo, group_repo)
    create_user_uc = CreateUserUseCase(user_repo)
    list_users_uc = ListUsersUseCase(user_repo)
    change_password_uc = ChangePasswordUseCase(user_repo)

    update_user_uc = UpdateUserUseCase(user_repo)
    delete_user_uc = DeleteUserUseCase(user_repo, api_key_repo)
    create_group_uc = CreateUserGroupUseCase(group_repo)
    list_groups_uc = ListUserGroupsUseCase(group_repo)
    get_group_uc = GetUserGroupUseCase(group_repo)
    update_group_uc = UpdateUserGroupUseCase(group_repo)
    delete_group_uc = DeleteUserGroupUseCase(group_repo)
    add_member_uc = AddUserToGroupUseCase(group_repo, user_repo)
    remove_member_uc = RemoveUserFromGroupUseCase(group_repo, user_repo)

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
        update_user_uc=update_user_uc,
        delete_user_uc=delete_user_uc,
        create_group_uc=create_group_uc,
        list_groups_uc=list_groups_uc,
        get_group_uc=get_group_uc,
        update_group_uc=update_group_uc,
        delete_group_uc=delete_group_uc,
        add_member_uc=add_member_uc,
        remove_member_uc=remove_member_uc,
    )

    # -- Node group use cases --
    list_node_groups_uc = ListNodeGroupsUseCase(node_group_repo)
    get_node_group_uc = GetNodeGroupUseCase(node_group_repo)
    create_node_group_uc = CreateNodeGroupUseCase(node_group_repo, node_repo, wazuh_client, puppet_nc_client)
    delete_node_group_uc = DeleteNodeGroupUseCase(node_group_repo, wazuh_client, puppet_nc_client)
    add_node_to_group_uc = AddNodeToGroupUseCase(node_group_repo, node_repo)
    remove_node_from_group_uc = RemoveNodeFromGroupUseCase(node_group_repo, node_repo)

    node_groups_routes.set_use_cases(
        list_uc=list_node_groups_uc,
        get_uc=get_node_group_uc,
        create_uc=create_node_group_uc,
        delete_uc=delete_node_group_uc,
        add_node_uc=add_node_to_group_uc,
        remove_node_uc=remove_node_from_group_uc,
    )

    # -- WebSocket manager --
    ws_manager = WebSocketManager(job_repo)

    # -- SSH + Ansible clients --
    ssh_client = SshClientAdapter(settings.ssh_key_path)
    ansible = AnsibleAdapter(settings.ansible_dir, settings.ssh_key_path, settings.packages_dir)

    # -- Job infrastructure (needed by both node and provisioning use cases) --
    start_job_uc = StartJobUseCase(job_repo, node_repo, ansible, ws_manager)
    detect_agents_uc = DetectAgentsUseCase(start_job_uc, node_repo, job_repo)

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
        platform_config_repo,
        puppet_master_host_env=settings.puppet_master_host,
        wazuh_manager_host_env=settings.wazuh_manager_host,
    )
    fix_dns_uc = FixNodeDnsUseCase(
        node_repo, ssh_client,
        platform_config_repo,
        puppet_master_host_env=settings.puppet_master_host,
        wazuh_manager_host_env=settings.wazuh_manager_host,
    )
    change_identity_uc = ChangeNodeIdentityUseCase(node_repo, ssh_client)

    nodes_routes.set_use_cases(
        register_uc=register_node_uc,
        get_uc=get_node_uc,
        list_uc=list_nodes_uc,
        ping_uc=ping_node_uc,
        ping_all_uc=ping_all_uc,
        update_uc=update_node_uc,
        delete_uc=delete_node_uc,
        check_dns_uc=check_dns_uc,
        fix_dns_uc=fix_dns_uc,
        change_identity_uc=change_identity_uc,
        detect_agents_uc=detect_agents_uc,
    )

    # -- Provisioning / infrastructure use cases --
    get_infra_status_uc = GetInfrastructureStatusUseCase(
        platform_config_repo,
        settings.puppet_master_host,
        settings.wazuh_manager_host,
        settings.puppet_master_port,
        settings.wazuh_api_port,
    )
    set_master_host_uc = SetMasterHostUseCase(
        platform_config_repo,
        settings.puppet_master_port,
        settings.wazuh_api_port,
    )
    list_jobs_uc = ListJobsUseCase(job_repo)
    get_job_uc = GetJobUseCase(job_repo)
    cancel_job_uc = CancelJobUseCase(job_repo, ansible)

    install_puppet_master_uc = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "puppet_master")
    install_wazuh_manager_uc = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "wazuh_manager")
    install_puppet_agent_uc  = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "puppet_agent")
    install_wazuh_agent_uc   = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "wazuh_agent")
    check_health_uc          = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "check_health")
    inspec_uc                = InspecControllerUseCase(node_repo, settings.ssh_key_path)

    infrastructure_routes.set_use_cases(
        get_status_uc=get_infra_status_uc,
        set_master_uc=set_master_host_uc,
        install_puppet_master_uc=install_puppet_master_uc,
        install_wazuh_manager_uc=install_wazuh_manager_uc,
        install_puppet_agent_uc=install_puppet_agent_uc,
        install_wazuh_agent_uc=install_wazuh_agent_uc,
        check_health_uc=check_health_uc,
        inspec_uc=inspec_uc,
        node_repo=node_repo,
        packages_dir=settings.packages_dir,
    )
    jobs_routes.set_use_cases(
        list_uc=list_jobs_uc,
        get_uc=get_job_uc,
        cancel_uc=cancel_job_uc,
        ws_manager=ws_manager,
    )

    # -- Compliance use cases --
    compliance_routes.set_use_cases(
        summary_uc=GetComplianceSummaryUseCase(compliance_repo),
        node_uc=GetNodeComplianceUseCase(node_repo, compliance_repo),
        collect_uc=CollectNodeComplianceUseCase(node_repo, compliance_repo, ssh_client),
        remediate_uc=TriggerRemediationUseCase(node_repo, compliance_repo, ssh_client),
    )

    # -- Attach audit repo to middleware --
    app.state.audit_repo = audit_repo

    # -- Bootstrap: seed default groups BEFORE init admin user --
    try:
        await SeedDefaultGroupsUseCase(group_repo).execute()
    except Exception as exc:
        logger.debug("Default group seeding: %s", exc)

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

    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SABC Compliance Platform API",
        version="1.0.0",
        description="""
## SABC Integrated Linux Compliance Platform

Manages a fleet of Linux servers (Rocky Linux 9 + Ubuntu 22.04) with automated
compliance enforcement across **CIS Benchmarks**, **ISO/IEC 27001**, and **PCI-DSS**.

### Closed Feedback Loop
Wazuh detects a violation → webhook → Puppet remediation → recorded result.

### Authentication
Two methods accepted on all protected endpoints:
- `X-API-Key: sabc_...` — machine-to-machine API key
- `Authorization: Bearer <jwt>` — user session token (from POST /auth/login)
        """,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health", "description": "Platform health checks"},
            {"name": "Auth", "description": "Authentication — API keys and user login"},
            {"name": "Nodes", "description": "Linux server node registry"},
            {"name": "Node Groups", "description": "Node group management with Wazuh and Puppet NC sync"},
            {"name": "Infrastructure", "description": "Puppet and Wazuh infrastructure setup"},
            {"name": "Jobs", "description": "Ansible provisioning jobs and log streaming"},
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
    app.add_middleware(AuditMiddleware)

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

    app.include_router(auth_routes.router)
    app.include_router(nodes_routes.router)
    app.include_router(node_groups_routes.router)
    app.include_router(infrastructure_routes.router)
    app.include_router(jobs_routes.router)
    app.include_router(compliance_routes.router)

    from fastapi import APIRouter
    health_router = APIRouter(tags=["Health"])

    @health_router.get("/health", summary="Platform health check")
    async def health():
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
