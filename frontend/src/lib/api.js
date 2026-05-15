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
  localStorage.setItem('bdc_api_key', key)
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

export function isAuthenticated() {
  return !!getJwt()
}

export function logout() {
  localStorage.removeItem('bdc_jwt_token')
}

async function request(method, path, body) {
  const base = getGatewayUrl()
  const url = `${base}${path}`

  const headers = {
    'Content-Type': 'application/json',
  }

  // JWT Bearer takes priority, fall back to API key
  const jwt = getJwt()
  const apiKey = getStoredApiKey()
  if (jwt) {
    headers['Authorization'] = `Bearer ${jwt}`
  } else if (apiKey) {
    headers['X-API-Key'] = apiKey
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
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return data
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const data = await request('POST', '/auth/login', { username, password })
  setJwt(data.access_token)
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

// ── Jobs ──────────────────────────────────────────────────────────────────────

export async function listJobs(limit = 50) {
  return request('GET', `/jobs?limit=${limit}`)
}

export async function getJob(id) {
  return request('GET', `/jobs/${id}`)
}

export async function getJobLogs(id, since = 0) {
  return request('GET', `/jobs/${id}/logs?since=${since}`)
}

export async function createJob(data) {
  return request('POST', '/provision', data)
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
