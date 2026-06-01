import config from '../config.js'

export function getGatewayUrl() {
  return localStorage.getItem('bdc_gateway_url') || config.apiBase
}

export function setGatewayUrl(url) {
  localStorage.setItem('bdc_gateway_url', url)
}

export function getStoredApiKey() {
  return localStorage.getItem('bdc_api_key') || ''
}

export function setApiKey(key) {
  if (key) {
    localStorage.setItem('bdc_api_key', key)
  } else {
    localStorage.removeItem('bdc_api_key')
  }
}

export function clearApiKey() {
  localStorage.removeItem('bdc_api_key')
}

export function getJwt() {
  return localStorage.getItem('bdc_jwt_token') || ''
}

export function setJwt(token) {
  if (token) {
    localStorage.setItem('bdc_jwt_token', token)
  } else {
    localStorage.removeItem('bdc_jwt_token')
  }
}

export function getUserRole() {
  return localStorage.getItem('bdc_user_role') || ''
}

export function getUsername() {
  return localStorage.getItem('bdc_user_username') || ''
}

export function isAuthenticated() {
  return !!getJwt()
}

export function logout() {
  localStorage.removeItem('bdc_jwt_token')
  localStorage.removeItem('bdc_user_role')
  localStorage.removeItem('bdc_user_username')
  localStorage.removeItem('bdc_api_key')
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
  if (data.role)     localStorage.setItem('bdc_user_role', data.role)
  if (data.username) localStorage.setItem('bdc_user_username', data.username)
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

export async function checkNodeDns(id) {
  return request('POST', `/nodes/${id}/check-dns`)
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

// ── Compliance ────────────────────────────────────────────────────────────────

export async function getComplianceSummary() {
  return request('GET', '/compliance/summary')
}

export async function getNodeCompliance(id) {
  return request('GET', `/compliance/nodes/${id}`)
}

export async function triggerRemediation(id, description) {
  return request('POST', `/compliance/nodes/${id}/remediate`, { description })
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

// ── Audit ─────────────────────────────────────────────────────────────────────

export async function getAuditLog(limit = 100) {
  return request('GET', `/audit?limit=${limit}`)
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth() {
  return request('GET', '/health')
}
