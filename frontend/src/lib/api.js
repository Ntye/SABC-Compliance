import config from '../config.js'

export function getGatewayUrl() {
  return localStorage.getItem('sabc_gateway_url') || config.apiBase
}

export function setGatewayUrl(url) {
  localStorage.setItem('sabc_gateway_url', url)
}

export function getStoredApiKey() {
  return localStorage.getItem('sabc_api_key') || ''
}

export function setApiKey(key) {
  if (key) {
    localStorage.setItem('sabc_api_key', key)
  } else {
    localStorage.removeItem('sabc_api_key')
  }
}

export function clearApiKey() {
  localStorage.removeItem('sabc_api_key')
}

export function getJwt() {
  return localStorage.getItem('sabc_jwt_token') || ''
}

export function setJwt(token) {
  if (token) {
    localStorage.setItem('sabc_jwt_token', token)
  } else {
    localStorage.removeItem('sabc_jwt_token')
  }
}

export function getUserRole() {
  return localStorage.getItem('sabc_user_role') || ''
}

export function getUsername() {
  return localStorage.getItem('sabc_user_username') || ''
}

export function isAuthenticated() {
  return !!getJwt()
}

export function logout() {
  localStorage.removeItem('sabc_jwt_token')
  localStorage.removeItem('sabc_user_role')
  localStorage.removeItem('sabc_user_username')
  localStorage.removeItem('sabc_api_key')
}

async function request(method, path, body) {
  const base = getGatewayUrl()
  const url = `${base}${path}`

  const headers = {
    'Content-Type': 'application/json',
  }

  // API key (if applied) grants action access. JWT is sent as identity
  // fallback so the backend can still recognise the user for read-only views.
  // The backend prefers X-API-Key when both are present.
  const jwt = getJwt()
  const apiKey = getStoredApiKey()
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  if (jwt) {
    headers['Authorization'] = `Bearer ${jwt}`
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  let data
  try {
    data = await res.json()
  } catch {
    data = {}
  }

  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`
    // If 401, clear JWT so user gets redirected to login
    if (res.status === 401) {
      logout()
    }
    const text = typeof msg === 'string' ? msg : JSON.stringify(msg)
    const err = new Error(text.replace(/^API_KEY_REQUIRED:\s*/, ''))
    err.status = res.status
    err.apiKeyRequired = typeof text === 'string' && text.startsWith('API_KEY_REQUIRED')
    throw err
  }

  return data
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const data = await request('POST', '/auth/login', { username, password })
  setJwt(data.access_token)
  if (data.role)     localStorage.setItem('sabc_user_role', data.role)
  if (data.username) localStorage.setItem('sabc_user_username', data.username)
  // Auto-apply the personal API key returned by the server.
  // This replaces any stale key from a previous session.
  if (data.api_key) {
    localStorage.setItem('sabc_api_key', data.api_key)
  } else {
    localStorage.removeItem('sabc_api_key')
  }
  return data
}

export async function initApiKey() {
  return request('POST', '/auth/init')
}

export async function listApiKeys() {
  return request('GET', '/auth/keys')
}

export async function createApiKey(name, role) {
  return request('POST', '/auth/keys', { name, role })
}

export async function revokeApiKey(id) {
  return request('DELETE', `/auth/keys/${id}`)
}

export async function listUsers() {
  return request('GET', '/auth/users')
}

export async function createUser(data) {
  return request('POST', '/auth/users', data)
}

export async function changePassword(oldPassword, newPassword) {
  return request('POST', '/auth/users/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

export async function updateUser(id, data) {
  return request('PATCH', `/auth/users/${id}`, data)
}

export async function deleteUser(id) {
  return request('DELETE', `/auth/users/${id}`)
}

export async function listUserGroups() {
  return request('GET', '/auth/groups')
}

export async function createUserGroup(data) {
  return request('POST', '/auth/groups', data)
}

export async function updateUserGroup(id, data) {
  return request('PATCH', `/auth/groups/${id}`, data)
}

export async function deleteUserGroup(id) {
  return request('DELETE', `/auth/groups/${id}`)
}

export async function getUserGroup(id) {
  return request('GET', `/auth/groups/${id}`)
}

export async function addGroupMember(groupId, userId) {
  return request('POST', `/auth/groups/${groupId}/members`, { user_id: userId })
}

export async function removeGroupMember(groupId, userId) {
  return request('DELETE', `/auth/groups/${groupId}/members/${userId}`)
}

// ── Nodes ─────────────────────────────────────────────────────────────────────

export async function listNodes(filters = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.os_family) params.set('os_family', filters.os_family)
  const qs = params.toString()
  return request('GET', `/nodes${qs ? '?' + qs : ''}`)
}

export async function getNode(id) {
  return request('GET', `/nodes/${id}`)
}

export async function registerNode(data) {
  return request('POST', '/nodes', data)
}

export async function pingNode(id) {
  return request('POST', `/nodes/${id}/ping`)
}

export async function pingAllNodes() {
  return request('POST', '/nodes/ping-all')
}

export async function updateNode(id, data) {
  return request('PATCH', `/nodes/${id}`, data)
}

export async function deleteNode(id) {
  return request('DELETE', `/nodes/${id}`)
}

export async function getHostInfo() {
  return request('GET', '/nodes/host-info')
}

export async function checkNodeDns(id) {
  return request('POST', `/nodes/${id}/check-dns`)
}

export async function fixNodeDns(id, checks) {
  return request('POST', `/nodes/${id}/fix-dns`, { checks })
}

export async function changeNodeIdentity(id, data) {
  // data: { ip?, hostname?, apply_system_hostname? }
  return request('POST', `/nodes/${id}/change-identity`, data)
}

export async function downloadSetupScript() {
  const base = getGatewayUrl()
  const headers = {}
  const apiKey = getStoredApiKey()
  const jwt = getJwt()
  if (apiKey) headers['X-API-Key'] = apiKey
  if (jwt) headers['Authorization'] = `Bearer ${jwt}`

  const res = await fetch(`${base}/nodes/setup-script`, { headers })
  if (!res.ok) throw new Error(`Failed to download script (HTTP ${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'setup-node.sh'
  a.click()
  URL.revokeObjectURL(url)
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export async function listJobs(limit = 50) {
  return request('GET', `/jobs?limit=${limit}`)
}

export async function getJob(id) {
  return request('GET', `/jobs/${id}`)
}

export async function cancelJob(id) {
  return request('POST', `/jobs/${id}/cancel`)
}

export function jobWsUrl(id) {
  return getGatewayUrl().replace(/^http/, 'ws') + `/jobs/${id}/ws`
}

// ── Infrastructure ────────────────────────────────────────────────────────────

export async function getInfrastructureStatus() {
  return request('GET', '/infrastructure/status')
}

export async function setPuppetMasterHost(host) {
  return request('POST', '/infrastructure/puppet-master', { host })
}

export async function setWazuhManagerHost(host) {
  return request('POST', '/infrastructure/wazuh-manager', { host })
}

export async function installService(service, nodeId) {
  // service: 'puppet-master' | 'wazuh-manager' | 'puppet-agent' | 'wazuh-agent'
  return request('POST', `/infrastructure/install/${service}`, { node_id: nodeId })
}

export async function checkPuppetAgentPlatform(nodeId) {
  return request('GET', `/infrastructure/puppet-agent/platform-check?node_id=${encodeURIComponent(nodeId)}`)
}

// ── Scan engine (platform / controller) ──────────────────────────────────────
// CINC Auditor runs only on the SABC platform server and reaches each node
// over SSH — no installation required on the managed nodes.

export async function getScanEngineStatus() {
  return request('GET', '/infrastructure/scan-engine/status')
}

export async function installScanEngineOnController() {
  return request('POST', '/infrastructure/scan-engine/install')
}

export async function verifyScanEngineAllNodes() {
  return request('POST', '/infrastructure/scan-engine/verify')
}

export async function verifyScanEngineNode(nodeId) {
  return request('POST', `/infrastructure/scan-engine/verify/${encodeURIComponent(nodeId)}`)
}

export async function checkNodeHealth(nodeId) {
  return request('POST', '/infrastructure/check-health', { node_id: nodeId })
}

// ── Compliance ────────────────────────────────────────────────────────────────

export async function getComplianceSummary() {
  return request('GET', '/compliance/summary')
}

export async function getNodeCompliance(id) {
  return request('GET', `/compliance/nodes/${id}`)
}

export async function collectNodeCompliance(id, profileId = null) {
  return request('POST', `/compliance/nodes/${id}/collect`, profileId ? { profile_id: profileId } : undefined)
}

export async function triggerRemediation(id, description) {
  return request('POST', `/compliance/nodes/${id}/remediate`, { description })
}

export async function getAutoScanSchedule() {
  return request('GET', '/compliance/schedule')
}

export async function setAutoScanSchedule({ enabled, interval, unit }) {
  return request('PUT', '/compliance/schedule', { enabled, interval, unit })
}

// ── Rules ─────────────────────────────────────────────────────────────────────

export async function listRules(filters = {}) {
  const params = new URLSearchParams()
  if (filters.framework) params.set('framework', filters.framework)
  if (filters.active !== undefined) params.set('active', String(filters.active))
  if (filters.os_family) params.set('os_family', filters.os_family)
  const qs = params.toString()
  return request('GET', `/rules${qs ? '?' + qs : ''}`)
}

export async function getRule(id) {
  return request('GET', `/rules/${id}`)
}

export async function createRule(data) {
  return request('POST', '/rules', data)
}

export async function updateRule(id, data) {
  return request('PATCH', `/rules/${id}`, data)
}

export async function deleteRule(id) {
  return request('DELETE', `/rules/${id}`)
}

// ── Compliance Profiles (referentials) ─────────────────────────────────────────

export async function listProfiles() {
  return request('GET', '/profiles')
}

export async function getProfile(id) {
  return request('GET', `/profiles/${id}`)
}

export async function createProfile(data) {
  return request('POST', '/profiles', data)
}

export async function updateProfile(id, data) {
  return request('PATCH', `/profiles/${id}`, data)
}

export async function deleteProfile(id) {
  return request('DELETE', `/profiles/${id}`)
}

export async function revertProfile(id) {
  return request('POST', `/profiles/${id}/revert`)
}

export async function addProfileControl(profileId, data) {
  return request('POST', `/profiles/${profileId}/controls`, data)
}

export async function updateProfileControl(profileId, controlId, data) {
  return request('PATCH', `/profiles/${profileId}/controls/${controlId}`, data)
}

export async function deleteProfileControl(profileId, controlId) {
  return request('DELETE', `/profiles/${profileId}/controls/${controlId}`)
}

export async function searchAllControls(q, limit = 40) {
  return request('GET', `/profiles/-/controls?q=${encodeURIComponent(q)}&limit=${limit}`)
}

export async function getControlHistory(profileId, controlId) {
  return request('GET', `/profiles/${profileId}/controls/${controlId}/history`)
}

export async function importScanControls(profileId) {
  return request('POST', `/profiles/${profileId}/import-scan-controls`)
}

// ── Audit ─────────────────────────────────────────────────────────────────────

export async function getAuditLog(limit = 100) {
  return request('GET', `/audit?limit=${limit}`)
}

// ── Settings: TLS certificate ───────────────────────────────────────────────

export async function getTlsCertificate() {
  return request('GET', '/settings/tls/certificate')
}

export async function uploadTlsCertificate(certFile, keyFile) {
  // multipart/form-data — do NOT set Content-Type so the browser adds the
  // multipart boundary itself. Mirrors the auth headers used by request().
  const base = getGatewayUrl()
  const headers = {}
  const apiKey = getStoredApiKey()
  const jwt = getJwt()
  if (apiKey) headers['X-API-Key'] = apiKey
  if (jwt) headers['Authorization'] = `Bearer ${jwt}`

  const form = new FormData()
  form.append('certificate', certFile)
  form.append('private_key', keyFile)

  const res = await fetch(`${base}/settings/tls/certificate`, {
    method: 'POST',
    headers,
    body: form,
  })
  let data
  try { data = await res.json() } catch { data = {} }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`
    if (res.status === 401) logout()
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth() {
  return request('GET', '/health')
}

// ── Node Groups ───────────────────────────────────────────────────────────────

export async function listNodeGroups() {
  return request('GET', '/node-groups')
}

export async function createNodeGroup(data) {
  return request('POST', '/node-groups', data)
}

export async function updateNodeGroup(id, data) {
  return request('PATCH', `/node-groups/${id}`, data)
}

export async function deleteNodeGroup(id) {
  return request('DELETE', `/node-groups/${id}`)
}

export async function getNodeGroup(id) {
  return request('GET', `/node-groups/${id}`)
}

export async function listNodeGroupFacts() {
  return request('GET', '/node-groups/facts')
}

export async function previewNodeGroupMatches(data) {
  return request('POST', '/node-groups/preview', data)
}

export async function addNodeToGroup(groupId, nodeId) {
  return request('POST', `/node-groups/${groupId}/nodes`, { node_id: nodeId })
}

export async function removeNodeFromGroup(groupId, nodeId) {
  return request('DELETE', `/node-groups/${groupId}/nodes/${nodeId}`)
}
