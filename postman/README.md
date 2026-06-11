# Postman collections — Wazuh & Puppet Enterprise APIs

Two comprehensive Postman collections (v2.1 schema) for probing the upstream
APIs that SABC-Compliance integrates with, each with a matching environment so
hosts/credentials/tokens are configured once and reused everywhere.

| File | Requests | Folders (by API) |
|------|---------:|------------------|
| `Wazuh.postman.json`  | 174 | Default, Security, Agents, Groups, Manager, Cluster, Decoders, Rules, CDB Lists, SCA, Syscheck (FIM), Rootcheck, Syscollector, Active Response, MITRE ATT&CK, Tasks, CIS-CAT, Logtest, Vulnerability detector (legacy ≤4.7), Experimental, Events |
| `Puppet.postman.json` | 132 | RBAC, Activity Service, Node Classifier, Orchestrator, PuppetDB, Code Manager, Puppet Server/Master, Puppet CA |

Environments:
- `Wazuh.postman_environment.json`
- `Puppet.postman_environment.json`

## Import

1. Postman → **Import** → drop all four `*.json` files.
2. Top-right environment selector → choose **Wazuh** or **Puppet**.
3. Disable TLS verification for self-signed certs: **Settings → General → SSL
   certificate verification → OFF** (or add the relevant CA cert under
   **Settings → Certificates**).

## Wazuh

Single API on **port 55000** over HTTPS, JWT-authenticated.

1. Set `wazuhHost`, `wazuhUser` (default `wazuh`), `wazuhPassword`.
2. Run **Security → Login (get JWT)**. A test script stores the JWT in `token`;
   every other request inherits `Authorization: Bearer {{token}}` from the
   collection auth.
3. JWT TTL is 900s by default — re-run Login on HTTP 401.

`baseUrl` is composed as `{{wazuhProtocol}}://{{wazuhHost}}:{{wazuhApiPort}}`.
The `agentId`, `groupId`, `nodeId` variables stand in for path params.

> Matches the platform config in `backend/src/config.py`
> (`wazuh_api_port=55000`, `wazuh_api_user=wazuh`) and the REST calls in
> `backend/ansible/playbooks/install_wazuh_agent.yml`.

## Puppet Enterprise

PE splits its APIs across **several services and ports**, all reachable on the
primary server FQDN (`puppetHost`):

| Service | Port | Collection variable |
|---------|-----:|---------------------|
| RBAC / Activity / Node Classifier | 4433 | `rbacUrl` |
| Orchestrator | 8143 | `orchestratorUrl` |
| PuppetDB | 8081 | `puppetdbUrl` |
| Code Manager | 8170 | `codeManagerUrl` |
| Puppet Server / CA | 8140 | `puppetserverUrl` |

1. Set `puppetHost`, `puppetLogin` (default `admin`), `puppetPassword`.
2. Run **RBAC API → Generate auth token**. A test script stores the RBAC token
   in `token`; PE service requests inherit `X-Authentication: {{token}}` from
   the collection auth.
3. For Code Manager, set `codeManagerToken` (a token with code-deploy
   permission) — those requests override auth to use it.

### Auth caveats
- **PuppetDB** and **Puppet Server / CA** normally require client-certificate
  (mTLS) auth. A token works only if the certname is whitelisted
  (`rbac-allowed`) on those services; otherwise attach a client cert in Postman
  (**Settings → Certificates**).
- The **Code Manager webhook** authenticates via the `token` query param (plus
  optional provider HMAC), not the header.
- **PQL/AST queries** for PuppetDB go in the `query` GET param or the POST body.

> Matches the platform config in `backend/src/config.py`
> (`puppet_master_port=8143`, `puppet_rbac_port=4433`, `puppet_admin_user=admin`).

## Notes on coverage & versions

- Wazuh folders follow the v4.x OpenAPI tag layout. The **Vulnerability
  detector** folder is the legacy ≤4.7 API; from 4.8 vulnerability data is
  served by the Wazuh indexer, not the server API.
- Puppet endpoints follow the long-stable PE service API surface (RBAC v1/v2,
  classifier v1/v2, orchestrator v1, PuppetDB v4, code-manager v1, puppet v3,
  puppet-ca v1) used through PE 2025.x.
- Example request bodies and query params are illustrative — adjust IDs,
  certnames, environments, and payloads to your infrastructure.
