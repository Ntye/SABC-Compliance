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
    ApiKeyRepository, AuditRepository, ComplianceGroupRepository, ComplianceRepository,
    DetectionRepository, JobRepository, NodeRepository, NodeGroupRepository,
    NotificationRepository, PlatformConfigRepository, ProfileRepository,
    RuleRepository, TierRepository, UserRepository, UserGroupRepository, create_db,
)
from infrastructure.http.puppet_nc_client import PuppetNCClient
from infrastructure.http.puppet_core_client import PuppetCoreClient
from infrastructure.http.ollama_client import OllamaClient
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
    CreateNodeGroupUseCase, UpdateNodeGroupUseCase, DeleteNodeGroupUseCase,
    ListNodeGroupsUseCase, GetNodeGroupUseCase, AddNodeToGroupUseCase,
    RemoveNodeFromGroupUseCase, ListFactsUseCase, PreviewMatchingUseCase,
    SeedDefaultNodeGroupsUseCase, SyncAllNodeGroupsUseCase,
    ApplyGroupPackageRepoUseCase,
)
from core.events import EventBus
from infrastructure.ssh.adapter import SshClientAdapter
from infrastructure.ansible.adapter import AnsibleAdapter
from modules.nodes.usecases import (
    ChangeNodeIdentityUseCase, CheckNodeDnsUseCase, DeleteNodeUseCase,
    FixNodeDnsUseCase, GetNodeUseCase, ListNodesUseCase,
    PingAllNodesUseCase, PingNodeUseCase, RegisterNodeUseCase,
    UpdateNodeUseCase,
)
from modules.provisioning.usecases import (
    CancelJobUseCase, DetectAgentsUseCase, GetInfrastructureStatusUseCase,
    GetJobUseCase, ScanEngineUseCase, InstallServiceUseCase, ListJobsUseCase,
    SetMasterHostUseCase, StartJobUseCase, SwitchPuppetEditionUseCase,
)
from modules.compliance.usecases import (
    CollectNodeComplianceUseCase, EnforceReferentialUseCase,
    GetComplianceHistoryUseCase, GetComplianceReportUseCase,
    GetComplianceSummaryUseCase, GetNodeComplianceUseCase,
    ScanComplianceGroupUseCase, TriggerRemediationUseCase, RunClosedLoopUseCase,
)
from modules.compliance.scheduler import AutoScanScheduler
from modules.detection.usecases import (
    GetConfigBlobUseCase, GetNodeDetectionStatusUseCase,
    ListDetectionEventsUseCase, ReceiveDetectionEventUseCase,
)
from modules.profiles.usecases import ProfileUseCases
from modules.tiers.usecases import (
    AssignGroupTierUseCase, AssignNodeTierUseCase, CreateTierUseCase,
    DeleteTierUseCase, GetTierUseCase,
    ListTiersUseCase, SeedSystemTiersUseCase, UpdateTierUseCase,
)
from modules.compliance_groups.usecases import (
    AddGroupMemberUseCase, CreateComplianceGroupUseCase, DeleteComplianceGroupUseCase,
    GetComplianceGroupUseCase, ListComplianceGroupsUseCase, RemoveGroupMemberUseCase,
    UpdateComplianceGroupUseCase,
)
from modules.settings.usecases import DistributeCertificateUseCase, TlsCertificateUseCase
from interface.http.routes import auth as auth_routes
from interface.http.routes import nodes as nodes_routes
from interface.http.routes import infrastructure as infrastructure_routes
from interface.http.routes import jobs as jobs_routes
from interface.http.routes import compliance as compliance_routes
from interface.http.routes import node_groups as node_groups_routes
from interface.http.routes import profiles as profiles_routes
from interface.http.routes import settings as settings_routes
from interface.http.routes import assistant as assistant_routes
from interface.http.routes import detection as detection_routes
from interface.http.routes import tiers as tiers_routes
from interface.http.routes import compliance_groups as compliance_groups_routes
from interface.http.routes import webhooks as webhooks_routes
from interface.http.routes import audit as audit_routes
from interface.http.routes import notifications as notifications_routes
from interface.http.middleware import AuditMiddleware, RateLimitMiddleware
from interface.websocket.manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_BANNER = """
╔══════════════════════════════════════════════════════╗
║                   CRICLO   v1.0.0                    ║
║              Linux Compliance Platform               ║
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
    engine, session_factory = await create_db(settings.db_path, settings.database_url)

    # -- Repositories --
    node_repo = NodeRepository(session_factory)
    job_repo = JobRepository(session_factory)
    compliance_repo = ComplianceRepository(session_factory)
    api_key_repo = ApiKeyRepository(session_factory)
    user_repo = UserRepository(session_factory)
    audit_repo = AuditRepository(session_factory)
    rule_repo = RuleRepository(session_factory)
    profile_repo = ProfileRepository(session_factory)
    platform_config_repo = PlatformConfigRepository(session_factory)
    group_repo = UserGroupRepository(session_factory)
    node_group_repo = NodeGroupRepository(session_factory)
    detection_repo = DetectionRepository(session_factory)
    tier_repo = TierRepository(session_factory)
    compliance_group_repo = ComplianceGroupRepository(session_factory)
    notification_repo = NotificationRepository(session_factory)

    # -- External service clients --
    puppet_nc_client = PuppetNCClient(
        host=settings.puppet_master_host,
        rbac_port=settings.puppet_rbac_port,
        admin_user=settings.puppet_admin_user,
        admin_pass=settings.puppet_admin_pass,
        token_rotate_seconds=settings.puppet_token_rotate_seconds,
        # Resolve the master host + PE console password from the platform-config
        # DB at call time — they're written there when the operator installs the
        # master through the console, not via the startup env vars.
        config_repo=platform_config_repo,
    )
    ollama_client = OllamaClient(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
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

    # -- SSH client (needed by the Puppet Core ENC classifier below) --
    ssh_client = SshClientAdapter(settings.ssh_key_path)

    # Puppet Core (open-source) node classifier — deploys an ENC over SSH
    # instead of calling the PE-only RBAC/Node-Classifier APIs. Used only when
    # puppet_edition == "core"; harmless to construct otherwise.
    puppet_core_client = PuppetCoreClient(
        ssh_client=ssh_client,
        host=settings.puppet_master_host,
        ssh_user=settings.puppet_core_ssh_user,
        ssh_key_path=settings.ssh_key_path,
        enc_dir=settings.puppet_core_enc_dir,
        default_environment=settings.puppet_core_default_environment,
        config_repo=platform_config_repo,
    )

    # -- Node group use cases --
    list_node_groups_uc = ListNodeGroupsUseCase(node_group_repo, node_repo)
    get_node_group_uc = GetNodeGroupUseCase(node_group_repo, node_repo)
    create_node_group_uc = CreateNodeGroupUseCase(node_group_repo, node_repo, puppet_nc_client)
    update_node_group_uc = UpdateNodeGroupUseCase(node_group_repo, node_repo, puppet_nc_client)
    delete_node_group_uc = DeleteNodeGroupUseCase(node_group_repo, puppet_nc_client)
    add_node_to_group_uc = AddNodeToGroupUseCase(node_group_repo, node_repo)
    remove_node_from_group_uc = RemoveNodeFromGroupUseCase(node_group_repo, node_repo)
    list_facts_uc = ListFactsUseCase(node_repo)
    preview_matching_uc = PreviewMatchingUseCase(node_repo)
    seed_node_groups_uc = SeedDefaultNodeGroupsUseCase(node_group_repo)
    sync_node_groups_uc = SyncAllNodeGroupsUseCase(
        node_group_repo, node_repo, puppet_nc_client,
        puppet_core_client=puppet_core_client, config_repo=platform_config_repo,
    )

    node_groups_routes.set_use_cases(
        list_uc=list_node_groups_uc,
        get_uc=get_node_group_uc,
        create_uc=create_node_group_uc,
        update_uc=update_node_group_uc,
        delete_uc=delete_node_group_uc,
        add_node_uc=add_node_to_group_uc,
        remove_node_uc=remove_node_from_group_uc,
        facts_uc=list_facts_uc,
        preview_uc=preview_matching_uc,
        seed_uc=seed_node_groups_uc,
        sync_uc=sync_node_groups_uc,
    )

    # -- WebSocket manager --
    ws_manager = WebSocketManager(job_repo)

    # -- Ansible client (ssh_client was created earlier for the ENC classifier) --
    ansible = AnsibleAdapter(settings.ansible_dir, settings.ssh_key_path, settings.packages_dir)

    # -- Job infrastructure (needed by both node and provisioning use cases) --
    start_job_uc = StartJobUseCase(job_repo, node_repo, ansible, ws_manager)
    detect_agents_uc = DetectAgentsUseCase(start_job_uc, node_repo, job_repo)

    # Package-repo enforcement per node group (Ansible; needs start_job_uc).
    apply_group_repo_uc = ApplyGroupPackageRepoUseCase(
        node_group_repo, node_repo, start_job_uc, platform_config_repo,
    )
    node_groups_routes.set_apply_repo_uc(apply_group_repo_uc)

    # -- Node use cases --
    # tier_repo validates the optional criticality tier picked at enrolment.
    register_node_uc = RegisterNodeUseCase(node_repo, ssh_client, event_bus, tier_repo=tier_repo)
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
    )
    fix_dns_uc = FixNodeDnsUseCase(
        node_repo, ssh_client,
        platform_config_repo,
        puppet_master_host_env=settings.puppet_master_host,
    )
    change_identity_uc = ChangeNodeIdentityUseCase(
        node_repo, ssh_client,
        platform_config=platform_config_repo,
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
        fix_dns_uc=fix_dns_uc,
        change_identity_uc=change_identity_uc,
        detect_agents_uc=detect_agents_uc,
    )

    # -- Provisioning / infrastructure use cases --
    get_infra_status_uc = GetInfrastructureStatusUseCase(
        platform_config_repo,
        settings.puppet_master_host,
        settings.puppet_master_port,
    )
    set_master_host_uc = SetMasterHostUseCase(
        platform_config_repo,
        settings.puppet_master_port,
    )
    list_jobs_uc = ListJobsUseCase(job_repo)
    get_job_uc = GetJobUseCase(job_repo)
    cancel_job_uc = CancelJobUseCase(job_repo, ansible)

    install_puppet_master_uc     = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "puppet_master")
    install_puppet_agent_uc      = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "puppet_agent")
    install_detection_agent_uc   = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "detection_agent")
    check_health_uc              = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "check_health")
    configure_puppet_core_enc_uc = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "puppet_core_enc")
    deploy_compliance_module_uc  = InstallServiceUseCase(start_job_uc, platform_config_repo, node_repo, "compliance_module")
    switch_puppet_edition_uc     = SwitchPuppetEditionUseCase(start_job_uc, platform_config_repo, node_repo, configure_puppet_core_enc_uc)
    scan_engine_uc               = ScanEngineUseCase(node_repo, settings.ssh_key_path)

    infrastructure_routes.set_use_cases(
        get_status_uc=get_infra_status_uc,
        set_master_uc=set_master_host_uc,
        install_puppet_master_uc=install_puppet_master_uc,
        configure_puppet_core_enc_uc=configure_puppet_core_enc_uc,
        deploy_compliance_module_uc=deploy_compliance_module_uc,
        switch_puppet_edition_uc=switch_puppet_edition_uc,
        install_puppet_agent_uc=install_puppet_agent_uc,
        install_detection_agent_uc=install_detection_agent_uc,
        check_health_uc=check_health_uc,
        scan_engine_uc=scan_engine_uc,
        node_repo=node_repo,
        packages_dir=settings.packages_dir,
        ssh_client=ssh_client,
        config_repo=platform_config_repo,
    )
    jobs_routes.set_use_cases(
        list_uc=list_jobs_uc,
        get_uc=get_job_uc,
        cancel_uc=cancel_job_uc,
        ws_manager=ws_manager,
    )

    # -- Compliance use cases --
    # Bundled scan profiles live under backend/scan-profiles/.
    _scan_profiles_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scan-profiles",
    )
    scan_profile_path = os.path.join(_scan_profiles_dir, "sabc-linux-baseline")

    # Section 6: map a profile → its generated InSpec directory. The built-in
    # SABC Baseline uses the generated multi-OS profile; the legacy internal/CIS
    # profiles fall back to the bundled sabc-linux-baseline for back-compat.
    from core.domain.entities import (
        CIS_BENCHMARK_PROFILE_ID as _CIS_ID,
        INTERNAL_PROFILE_ID as _INT_ID,
        SABC_BASELINE_PROFILE_ID as _BASE_ID,
    )

    def _inspec_dir_for(profile):
        mapping = {
            _BASE_ID: os.path.join(_scan_profiles_dir, "sabc-baseline"),
            _INT_ID: scan_profile_path,
            _CIS_ID: scan_profile_path,
        }
        d = mapping.get(profile.id)
        return d if d and os.path.isdir(d) else None

    from modules.compliance.scan_resolver import ScanPlanResolver
    scan_resolver = ScanPlanResolver(
        node_repo, compliance_group_repo, tier_repo, profile_repo,
        inspec_dir_for=_inspec_dir_for,
    )
    collect_uc = CollectNodeComplianceUseCase(
        node_repo, compliance_repo, ssh_client,
        default_ssh_key_path=settings.ssh_key_path,
        profile_path=scan_profile_path,
        scan_ctrl=scan_engine_uc,
        scan_resolver=scan_resolver,
    )
    # Section 6: scan a whole compliance group (members × bound profiles).
    scan_group_uc = ScanComplianceGroupUseCase(
        compliance_group_repo, node_repo, scan_resolver, collect_uc,
    )
    remediate_uc = TriggerRemediationUseCase(node_repo, compliance_repo, ssh_client)
    # Closed-loop engine — enforce (Puppet) → re-scan (CINC) for a single node or
    # every member of a node group. Group membership resolves via get_node_group_uc.
    closed_loop_uc = RunClosedLoopUseCase(
        node_repo=node_repo,
        remediate_uc=remediate_uc,
        collect_uc=collect_uc,
        get_group_uc=get_node_group_uc,
        event_bus=event_bus,
        ws_manager=ws_manager,
        concurrency=settings.closed_loop_concurrency,
    )
    # Enforce the generated sabc_hardening referential (tier- and family-scoped)
    # directly on a node or node group via an Ansible `puppet apply` job, so the
    # internal referential fully passes. Module source mirrors the seed-time
    # generation path (…/puppet/modules/sabc_hardening next to the ansible dir).
    _module_base = os.path.dirname(os.path.abspath(settings.ansible_dir or "/app/ansible"))
    enforce_uc = EnforceReferentialUseCase(
        node_repo=node_repo,
        start_job_uc=start_job_uc,
        scan_resolver=scan_resolver,
        profile_repo=profile_repo,
        module_src=os.path.join(_module_base, "puppet", "modules", "sabc_hardening"),
        get_group_uc=get_node_group_uc,
        # Tiers-page chain: notify when each enforcement job finishes, then run
        # a verification scan and notify its outcome (header bell).
        notification_repo=notification_repo,
        collect_uc=collect_uc,
    )
    compliance_routes.set_use_cases(
        summary_uc=GetComplianceSummaryUseCase(compliance_repo),
        node_uc=GetNodeComplianceUseCase(node_repo, compliance_repo),
        collect_uc=collect_uc,
        remediate_uc=remediate_uc,
        closed_loop_uc=closed_loop_uc,
        enforce_uc=enforce_uc,
        history_uc=GetComplianceHistoryUseCase(node_repo, compliance_repo),
        report_uc=GetComplianceReportUseCase(node_repo, compliance_repo),
        config_repo=platform_config_repo,
    )

    # -- Detection webhook receiver: detection → scan (→ optional remediation) --
    # The custom detection agent spots a config change → POST
    # /api/webhooks/detection → evidence stored (events + content-addressed
    # blobs) → suppression rules applied → a compliance scan always runs, and
    # Puppet enforcement runs only when the closed loop is enabled (global
    # config or a node group's active_response) → live WebSocket + event-bus.
    receive_detection_uc = ReceiveDetectionEventUseCase(
        node_repo=node_repo,
        detection_repo=detection_repo,
        compliance_repo=compliance_repo,
        remediate_uc=remediate_uc,
        collect_uc=collect_uc,
        config_repo=platform_config_repo,
        node_group_repo=node_group_repo,
        tier_repo=tier_repo,
        event_bus=event_bus,
        ws_manager=ws_manager,
    )
    webhooks_routes.set_use_cases(
        receive_detection_uc=receive_detection_uc,
        config_repo=platform_config_repo,
        webhook_api_key=settings.detection_webhook_api_key,
        allowed_source_ips=settings.detection_webhook_source_ip,
    )
    detection_routes.set_use_cases(
        list_events_uc=ListDetectionEventsUseCase(detection_repo, node_repo, compliance_repo),
        node_status_uc=GetNodeDetectionStatusUseCase(detection_repo, node_repo),
        blob_uc=GetConfigBlobUseCase(detection_repo),
    )

    # -- Auto-scan background scheduler (runs fleet-wide compliance on a timer) --
    auto_scan = AutoScanScheduler(
        collect_uc, node_repo, platform_config_repo,
        group_repo=compliance_group_repo, scan_group_uc=scan_group_uc,
    )
    auto_scan.start()

    # -- Compliance profiles (referentials) --
    profile_uc = ProfileUseCases(profile_repo)
    profiles_routes.set_use_cases(profile_uc)

    # -- Platform settings (TLS certificate management) --
    tls_cert_uc = TlsCertificateUseCase(settings.tls_certs_dir)
    distribute_cert_uc = DistributeCertificateUseCase(
        node_repo=node_repo,
        job_repo=job_repo,
        ws_manager=ws_manager,
        certs_dir=settings.tls_certs_dir,
        ssh_key_path=settings.ssh_key_path,
    )
    settings_routes.set_use_cases(tls_cert_uc=tls_cert_uc, distribute_cert_uc=distribute_cert_uc)

    # -- Tiers (criticality classification; CIS Level → node scope) --
    seed_tiers_uc = SeedSystemTiersUseCase(tier_repo, node_repo)
    tiers_routes.set_use_cases(
        list_uc=ListTiersUseCase(tier_repo),
        get_uc=GetTierUseCase(tier_repo),
        create_uc=CreateTierUseCase(tier_repo, profile_repo),
        update_uc=UpdateTierUseCase(tier_repo, profile_repo),
        delete_uc=DeleteTierUseCase(tier_repo, node_repo),
        assign_uc=AssignNodeTierUseCase(node_repo, tier_repo),
        assign_group_uc=AssignGroupTierUseCase(node_group_repo, node_repo, tier_repo),
    )

    # -- Compliance node groups (platform-only; never Puppet NC) --
    compliance_groups_routes.set_use_cases(
        list_uc=ListComplianceGroupsUseCase(compliance_group_repo),
        get_uc=GetComplianceGroupUseCase(compliance_group_repo),
        create_uc=CreateComplianceGroupUseCase(compliance_group_repo, profile_repo, node_repo),
        update_uc=UpdateComplianceGroupUseCase(compliance_group_repo, profile_repo, node_repo),
        delete_uc=DeleteComplianceGroupUseCase(compliance_group_repo),
        add_member_uc=AddGroupMemberUseCase(compliance_group_repo, node_repo),
        remove_member_uc=RemoveGroupMemberUseCase(compliance_group_repo),
        scan_uc=scan_group_uc,
    )

    # -- Offline AI assistant --
    assistant_routes.set_use_cases(ollama_client=ollama_client)

    # -- Attach audit repo to middleware --
    app.state.audit_repo = audit_repo
    audit_routes.set_repo(audit_repo)

    # -- Platform notifications (header bell) --
    notifications_routes.set_repo(notification_repo)

    # -- Bootstrap: seed default groups BEFORE init admin user --
    try:
        await SeedDefaultGroupsUseCase(group_repo).execute()
    except Exception as exc:
        logger.debug("Default group seeding: %s", exc)

    # -- Bootstrap: seed OS-family node group hierarchy, then push to Puppet
    #    so already-registered nodes are classified. Sync is best-effort: if the
    #    Puppet master is not yet reachable the groups stay marked unsynced and
    #    an admin can re-run it from the UI (POST /node-groups/sync).
    try:
        n = await seed_node_groups_uc.execute()
        if n:
            logger.info("Seeded %d default node groups", n)
        try:
            result = await sync_node_groups_uc.execute()
            logger.info(
                "Node group sync: %d/%d groups, %d node memberships classified",
                result.get("groups_synced", 0), result.get("groups_total", 0),
                result.get("nodes_classified", 0),
            )
        except Exception as exc:
            logger.debug("Node group sync (deferred to admin): %s", exc)
    except Exception as exc:
        logger.debug("Node group seeding: %s", exc)

    # -- Bootstrap: seed the built-in SABC hardening referential --
    try:
        await profile_uc.seed_builtin()
    except Exception as exc:
        logger.debug("Profile seeding: %s", exc)

    # -- Bootstrap: seed the built-in unified SABC Baseline (both OS families),
    #    then (re)generate the sabc_hardening Puppet module + sabc-baseline
    #    InSpec profile from it. Generation runs only when the referential was
    #    actually (re)seeded, so restarts don't rewrite the artifact tree.
    # -- Bootstrap: seed the two undeletable system tiers --
    try:
        n = await seed_tiers_uc.execute()
        if n:
            logger.info("Seeded %d system tier(s)", n)
    except Exception as exc:
        logger.debug("Tier seeding: %s", exc)

    try:
        from core.domain.entities import SABC_BASELINE_PROFILE_ID
        from modules.profiles.artifact_generator import GenerateBuiltinArtifactsUseCase
        from modules.profiles.seed_referentials import SeedSabcBaselineUseCase
        seeded = await SeedSabcBaselineUseCase(profile_repo, platform_config_repo).execute()
        if seeded:
            _base = os.path.dirname(os.path.abspath(settings.ansible_dir or "/app/ansible"))
            gen = GenerateBuiltinArtifactsUseCase(
                profile_repo,
                os.path.join(_base, "puppet", "modules", "sabc_hardening"),
                os.path.join(_base, "scan-profiles", "sabc-baseline"),
            )
            res = await gen.execute(SABC_BASELINE_PROFILE_ID)
            logger.info(
                "Generated built-in artifacts: %d files, %d control/family enforced, "
                "%d implementation-pending", res.files_written,
                len(res.generated), len(res.pending),
            )
    except Exception as exc:
        logger.debug("SABC Baseline seeding/generation: %s", exc)

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

    auto_scan.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CRICLO API",
        version="1.0.0",
        description="""
## CRICLO — Integrated Linux Compliance Platform

Manages a fleet of Linux servers (Rocky Linux 9 + Ubuntu 22.04) with automated
compliance enforcement across two frameworks: **CIS Benchmark** (built-in hardening
baseline) and **Internal Referential** (SABC company-specific baseline, independently
maintained and distinct from the CIS framework).

### Closed Feedback Loop
The SABC detection agent spots a config change → webhook → suppression rules →
Puppet remediation → recorded result.

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
            {"name": "Node Groups", "description": "Node group management with Puppet NC sync"},
            {"name": "Infrastructure", "description": "Puppet and detection agent infrastructure setup"},
            {"name": "Jobs", "description": "Ansible provisioning jobs and log streaming"},
            {"name": "Compliance", "description": "Compliance reports and remediation"},
            {"name": "Detection", "description": "Config-change events from the detection agents"},
            {"name": "Rules", "description": "Puppet compliance rules library"},
            {"name": "Audit", "description": "HTTP audit log"},
            {"name": "Notifications", "description": "In-platform notifications (header bell)"},
            {"name": "Webhooks", "description": "Internal webhook endpoints"},
            {"name": "Settings", "description": "Platform settings — TLS certificate management"},
            {"name": "Assistant", "description": "Offline AI assistant powered by Ollama (local LLM)"},
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
    app.include_router(profiles_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(assistant_routes.router)
    app.include_router(detection_routes.router)
    app.include_router(tiers_routes.router)
    app.include_router(compliance_groups_routes.router)
    app.include_router(webhooks_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(notifications_routes.router)

    from fastapi import APIRouter
    health_router = APIRouter(tags=["Health"])

    @health_router.get("/health", summary="Platform health check")
    async def health():
        return {
            "status": "up",
            "services": {
                "api": {"status": "up"},
                "puppet": {"status": "not_configured"},
                "detection": {"status": "not_configured"},
                "ansible": {"status": "unknown"},
            }
        }

    app.include_router(health_router)
    return app


app = create_app()
