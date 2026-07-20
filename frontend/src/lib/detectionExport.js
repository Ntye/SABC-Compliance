// Detection-events exporters — one column set feeds both JSON and CSV so the
// formats stay at parity by construction. Exporters take the ALREADY-FILTERED
// array from the page, so the active status/node filter is reflected in the
// file. Every export records an audit event via recordExport.
import { recordExport } from './api.js'
import { eventStatus } from '../hooks/usePosture.js'
import { downloadBlob } from './complianceExport.js'

const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
const toCsv = (rows) => rows.map((r) => r.map(csvCell).join(',')).join('\n')
const today = () => new Date().toISOString().slice(0, 10)

function actorLabel(actor) {
  if (!actor) return ''
  const label = actor.username || actor.comm || actor.exe || (actor.auid != null ? `auid ${actor.auid}` : '')
  const uid = actor.auid ?? actor.uid
  return uid != null ? `${label} (uid ${uid})` : label
}

// One row shape shared by both formats.
function eventRow(e) {
  return {
    hostname: e.hostname,
    path: e.path || '',
    event_type: e.event_type,
    status: eventStatus(e),
    timestamp: e.timestamp,
    actor: actorLabel(e.actor),
    prev_hash: e.prev_hash || '',
    new_hash: e.new_hash || '',
    suppress_reason: e.suppress_reason || '',
    violation_detail: e.violation_detail || '',
    remediation_outcome: e.remediation_outcome || '',
    recorded_at: e.created_at,
  }
}

function baseName(meta) {
  const parts = ['detection-events']
  if (meta.status) parts.push(meta.status)
  if (meta.hostname) parts.push(meta.hostname)
  parts.push(today())
  return parts.join('-').replace(/[^\w.-]+/g, '-')
}

function audit(events, meta, format) {
  recordExport({
    resource_type: 'detection',
    resource_id: meta.nodeId || undefined,
    resource_name: meta.hostname || 'Detection events',
    format,
    count: events.length,
  })
}

// meta: { status?: string, nodeId?: string, hostname?: string }
export function exportDetectionEventsJson(events, meta = {}) {
  const payload = {
    exported_at: new Date().toISOString(),
    filter: { status: meta.status || 'all', node: meta.hostname || 'all' },
    count: events.length,
    events: events.map(eventRow),
  }
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json', `${baseName(meta)}.json`)
  audit(events, meta, 'json')
}

export function exportDetectionEventsCsv(events, meta = {}) {
  const cols = [
    'hostname', 'path', 'event_type', 'status', 'timestamp', 'actor',
    'prev_hash', 'new_hash', 'suppress_reason', 'violation_detail',
    'remediation_outcome', 'recorded_at',
  ]
  const rows = [cols, ...events.map((e) => { const r = eventRow(e); return cols.map((c) => r[c]) })]
  downloadBlob(toCsv(rows), 'text/csv', `${baseName(meta)}.csv`)
  audit(events, meta, 'csv')
}
