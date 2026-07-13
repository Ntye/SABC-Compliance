// Shared compliance exporters — one column set feeds JSON, CSV and PDF so the
// three formats stay at parity by construction. Every exporter takes an
// already-filtered array, so whatever status/framework filter is active on the
// page is reflected in the file. All record an audit event via recordExport.
import { recordExport } from './api.js'
import { utcDate } from './time.js'

// ── low-level helpers ─────────────────────────────────────────────────────────

export function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
  ))
}

const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
const toCsv = (rows) => rows.map((r) => r.map(csvCell).join(',')).join('\n')
const today = () => new Date().toISOString().slice(0, 10)
const slug = (s) => (String(s || 'export').replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'export')

function openPrint(html) {
  const win = window.open('', '_blank')
  if (win) { win.document.write(html); win.document.close(); setTimeout(() => win.print(), 400) }
}

function scoreHex(score) {
  if (score == null) return '#6b7280'
  return score >= 90 ? '#16a34a' : score >= 70 ? '#f59e0b' : '#dc2626'
}

function fmtWhen(v) {
  if (!v) return ''
  const d = utcDate(v)
  return d ? d.toLocaleString() : String(v)
}

// ── control-level exports (node posture + a single historical report) ─────────
//
// Columns are identical across JSON/CSV/PDF. `controls` is the caller's already
// filtered list; `meta` carries node identity, the report summary, and a
// human-readable `filterLabel` describing the active filter (or null).

const CONTROL_COLUMNS = [
  'Control ID', 'Title', 'Status', 'Severity', 'CIS Level', 'Section', 'Description', 'Failure Detail',
]

const levelLabel = (lvl) => (lvl === 1 || lvl === 2 ? `Level ${lvl}` : '')

function controlCells(c) {
  return [
    c.control_id || '',
    c.title || '',
    c.status || '',
    c.severity || '',
    levelLabel(c.cis_level),
    c.section || '',
    c.desc || '',
    c.message || '',
  ]
}

function controlAudit(meta, format, count) {
  recordExport({
    resource_type: meta.resourceType || 'node',
    resource_id: meta.resourceId,
    resource_name: meta.resourceName || meta.hostname,
    format,
    count,
  })
}

function controlBaseName(meta) {
  return `sabc-scan-${slug(meta.hostname || meta.resourceName)}-${today()}`
}

export function exportControlsJson(controls, meta = {}) {
  const payload = {
    exported_at: new Date().toISOString(),
    node: { hostname: meta.hostname, ip: meta.ip, os_family: meta.os_family },
    filter: meta.filterLabel || null,
    report: {
      score: meta.score,
      passed_checks: meta.passed_checks,
      failed_checks: meta.failed_checks,
      skipped_checks: meta.skipped_checks,
      total_checks: meta.total_checks,
      source: meta.source,
      profile: meta.profile,
      collected_at: meta.collected_at,
      control_count: controls.length,
      controls: controls.map((c) => ({
        control_id: c.control_id,
        title: c.title,
        status: c.status,
        severity: c.severity || null,
        cis_level: c.cis_level ?? null,
        section: c.section || null,
        frameworks: c.frameworks || {},
        description: c.desc || '',
        failure_detail: c.message || '',
      })),
    },
  }
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json', `${controlBaseName(meta)}.json`)
  controlAudit(meta, 'json', controls.length)
}

export function exportControlsCsv(controls, meta = {}) {
  const rows = [CONTROL_COLUMNS, ...controls.map(controlCells)]
  downloadBlob(toCsv(rows), 'text/csv', `${controlBaseName(meta)}.csv`)
  controlAudit(meta, 'csv', controls.length)
}

export function exportControlsPdf(controls, meta = {}) {
  const body = controls.map((c) => {
    const color = c.status === 'fail' ? '#dc2626' : c.status === 'pass' ? '#16a34a' : '#6b7280'
    const bg = c.status === 'fail' ? '#fff5f5' : ''
    return `<tr style="background:${bg}">
      <td>${esc(c.control_id)}</td>
      <td>${esc(c.title)}</td>
      <td style="color:${color};font-weight:600">${esc(c.status)}</td>
      <td>${esc(c.severity || '')}</td>
      <td>${esc(levelLabel(c.cis_level))}</td>
      <td>${esc(c.section || '')}</td>
      <td>${esc(c.desc || '')}</td>
      <td>${esc(c.message || '')}</td>
    </tr>`
  }).join('')
  const filterNote = meta.filterLabel ? ` · Filter: ${esc(meta.filterLabel)}` : ''
  const html = `<!DOCTYPE html><html><head><title>CRICLO — ${esc(meta.hostname || meta.resourceName || 'Scan')}</title>
<style>
  body{font-family:sans-serif;font-size:10px;margin:24px;color:#111}
  h2{margin:0 0 4px}.meta{color:#555;margin-bottom:14px;font-size:11px}
  .score{font-size:22px;font-weight:700;color:${scoreHex(meta.score)}}
  table{width:100%;border-collapse:collapse;margin-top:10px}
  th,td{border:1px solid #e5e7eb;padding:5px 7px;text-align:left;vertical-align:top}
  th{background:#f9fafb;font-size:9px;font-weight:600;text-transform:uppercase}
  td:nth-child(7),td:nth-child(8){color:#444;max-width:260px}
  @media print{body{margin:0}}
</style></head><body>
<h2>CRICLO Compliance Report — ${esc(meta.hostname || meta.resourceName || '')}</h2>
<div class="meta">
  ${meta.ip ? `IP: ${esc(meta.ip)} · ` : ''}${meta.os_family ? `OS: ${esc(meta.os_family)} · ` : ''}
  Score: <span class="score">${meta.score ?? '—'}%</span> ·
  ${meta.passed_checks ?? 0} passed · ${meta.failed_checks ?? 0} failed ·
  ${controls.length} control(s)${filterNote} ·
  Scanned: ${esc(fmtWhen(meta.collected_at))}
</div>
<table><thead><tr>${CONTROL_COLUMNS.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
<tbody>${body}</tbody></table></body></html>`
  openPrint(html)
  controlAudit(meta, 'pdf', controls.length)
}

// ── fleet-level exports (one summary row per node) ────────────────────────────

function primaryReport(node) {
  const reports = node.reports || []
  return (
    reports.find((r) => r.source === 'scan') ||
    reports.find((r) => r.source === 'cis-ssh') ||
    reports.find((r) => r.source !== 'puppet') ||
    null
  )
}

const FLEET_COLUMNS = ['Node', 'IP', 'OS', 'Score (%)', 'Passed', 'Failed', 'Skipped', 'Source', 'Last Scan']

function fleetAudit(nodes, format) {
  recordExport({ resource_type: 'fleet', resource_name: 'Fleet compliance', format, count: nodes.length })
}

export function exportFleetJson(nodes, meta = {}) {
  const payload = {
    exported_at: new Date().toISOString(),
    filter: meta.filterLabel || null,
    node_count: nodes.length,
    nodes: nodes.map((node) => {
      const r = primaryReport(node)
      return {
        node_id: node.node_id,
        hostname: node.hostname,
        ip: node.ip,
        os_family: node.os_family,
        score: r?.score ?? null,
        passed_checks: r?.passed_checks ?? null,
        failed_checks: r?.failed_checks ?? null,
        skipped_checks: r?.skipped_checks ?? null,
        source: r?.source ?? null,
        collected_at: r?.collected_at ?? null,
      }
    }),
  }
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json', `sabc-fleet-${today()}.json`)
  fleetAudit(nodes, 'json')
}

export function exportFleetCsv(nodes, meta = {}) {
  const rows = [FLEET_COLUMNS]
  for (const node of nodes) {
    const r = primaryReport(node)
    rows.push([
      node.hostname, node.ip, node.os_family,
      r ? r.score : '', r ? r.passed_checks : '', r ? r.failed_checks : '',
      r ? (r.skipped_checks || 0) : '', r ? r.source : '',
      r ? utcDate(r.collected_at).toISOString() : '',
    ])
  }
  downloadBlob(toCsv(rows), 'text/csv', `sabc-fleet-${today()}.csv`)
  fleetAudit(nodes, 'csv')
}

export function exportFleetPdf(nodes, meta = {}) {
  const title = meta.title || 'Fleet compliance'
  const rows = nodes.map((node) => {
    const r = primaryReport(node)
    const score = r ? r.score : null
    return `<tr>
      <td><b>${esc(node.hostname)}</b><br/><small style="color:#666">${esc(node.ip)}</small></td>
      <td><span style="color:${scoreHex(score)};font-weight:700">${score !== null ? score + '%' : '—'}</span></td>
      <td>${r ? `<span style="color:#16a34a">${r.passed_checks}✓</span> <span style="color:#dc2626">${r.failed_checks}✗</span>` : '—'}</td>
      <td>${r ? esc(r.source) : '—'}</td>
      <td>${r ? esc(fmtWhen(r.collected_at)) : '—'}</td>
    </tr>`
  }).join('')
  const filterNote = meta.filterLabel ? ` · Filter: ${esc(meta.filterLabel)}` : ''
  const html = `<!DOCTYPE html><html><head><title>${esc(title)}</title>
<style>
  body{font-family:sans-serif;font-size:12px;margin:24px}
  h2{margin:0 0 4px}p{color:#666;margin:0 0 16px}
  table{width:100%;border-collapse:collapse}
  th,td{border:1px solid #e5e7eb;padding:6px 10px;text-align:left;vertical-align:top}
  th{background:#f9fafb;font-size:10px;font-weight:600;text-transform:uppercase}
  @media print{body{margin:0}}
</style></head><body>
<h2>${esc(title)}</h2><p>Generated: ${esc(new Date().toLocaleString())} · ${nodes.length} node(s)${filterNote}</p>
<table><thead><tr><th>Node</th><th>Score</th><th>Controls</th><th>Source</th><th>Last Scan</th></tr></thead>
<tbody>${rows}</tbody></table></body></html>`
  openPrint(html)
  fleetAudit(nodes, 'pdf')
}

// ── history exports (scan-history rows over a custom interval) ─────────────────

const HISTORY_COLUMNS = [
  'Scan ID', 'Node', 'Score (%)', 'Passed', 'Failed', 'Skipped', 'Total', 'Source', 'Profile', 'Scanned At',
]

function historyCells(r) {
  return [
    r.id,
    r.hostname || r.node_id || '',
    r.score,
    r.passed_checks,
    r.failed_checks,
    r.skipped_checks ?? '',
    r.total_checks,
    r.source || '',
    r.profile || '',
    r.collected_at ? utcDate(r.collected_at).toISOString() : '',
  ]
}

function historyMeta(meta) {
  const label = meta.label || (meta.nodeId ? meta.nodeId : 'fleet')
  return {
    base: `sabc-history-${slug(label)}-${today()}`,
    range: [meta.from, meta.to].filter(Boolean).map((v) => fmtWhen(v)).join(' → '),
    label,
  }
}

function historyAudit(rows, meta, format) {
  recordExport({
    resource_type: 'history',
    resource_id: meta.nodeId || undefined,
    resource_name: meta.label || (meta.nodeId ? meta.nodeId : 'Fleet'),
    format,
    count: rows.length,
  })
}

export function exportHistoryJson(rows, meta = {}) {
  const m = historyMeta(meta)
  const payload = {
    exported_at: new Date().toISOString(),
    scope: meta.nodeId ? 'node' : 'fleet',
    node: meta.label || null,
    from: meta.from || null,
    to: meta.to || null,
    scan_count: rows.length,
    scans: rows.map((r) => ({
      id: r.id,
      node_id: r.node_id,
      hostname: r.hostname || null,
      score: r.score,
      passed_checks: r.passed_checks,
      failed_checks: r.failed_checks,
      skipped_checks: r.skipped_checks ?? null,
      total_checks: r.total_checks,
      source: r.source || null,
      profile: r.profile || null,
      collected_at: r.collected_at,
    })),
  }
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json', `${m.base}.json`)
  historyAudit(rows, meta, 'json')
}

export function exportHistoryCsv(rows, meta = {}) {
  const m = historyMeta(meta)
  const table = [HISTORY_COLUMNS, ...rows.map(historyCells)]
  downloadBlob(toCsv(table), 'text/csv', `${m.base}.csv`)
  historyAudit(rows, meta, 'csv')
}

export function exportHistoryPdf(rows, meta = {}) {
  const m = historyMeta(meta)
  const body = rows.map((r) => `<tr>
      <td>${esc(fmtWhen(r.collected_at))}</td>
      <td>${esc(r.hostname || r.node_id || '')}</td>
      <td><span style="color:${scoreHex(r.score)};font-weight:700">${r.score}%</span></td>
      <td><span style="color:#16a34a">${r.passed_checks}✓</span> <span style="color:#dc2626">${r.failed_checks}✗</span></td>
      <td>${esc(r.source || '')}</td>
      <td>${esc(r.profile || '')}</td>
    </tr>`).join('')
  const rangeNote = m.range ? ` · ${esc(m.range)}` : ''
  const html = `<!DOCTYPE html><html><head><title>SABC scan history — ${esc(m.label)}</title>
<style>
  body{font-family:sans-serif;font-size:11px;margin:24px}
  h2{margin:0 0 4px}p{color:#666;margin:0 0 14px}
  table{width:100%;border-collapse:collapse}
  th,td{border:1px solid #e5e7eb;padding:5px 9px;text-align:left;vertical-align:top}
  th{background:#f9fafb;font-size:9px;font-weight:600;text-transform:uppercase}
  @media print{body{margin:0}}
</style></head><body>
<h2>SABC Scan History — ${esc(m.label)}</h2>
<p>Generated: ${esc(new Date().toLocaleString())} · ${rows.length} scan(s)${rangeNote}</p>
<table><thead><tr><th>Scanned At</th><th>Node</th><th>Score</th><th>Controls</th><th>Source</th><th>Profile</th></tr></thead>
<tbody>${body}</tbody></table></body></html>`
  openPrint(html)
  historyAudit(rows, meta, 'pdf')
}
