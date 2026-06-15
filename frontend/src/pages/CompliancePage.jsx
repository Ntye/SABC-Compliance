import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { ShieldCheck, RefreshCw, ChevronRight, AlertTriangle, Play, Download, ChevronDown } from 'lucide-react'
import { getComplianceSummary, collectNodeCompliance } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { badge, scoreColor, scoreBarColor } from '../lib/tw.js'

const C = { pass: '#16a34a', fail: '#dc2626', skip: '#9ca3af', high: '#dc2626' }

function primaryReport(node) {
  const reports = node.reports || []
  return (
    reports.find((r) => r.source === 'scan') ||
    reports.find((r) => r.source === 'cis-ssh') ||
    reports.find((r) => r.source !== 'puppet') ||
    null
  )
}

function sourceLabel(t, source) {
  if (source === 'scan') return t('compliance.sourceScan')
  if (source === 'cis-ssh') return t('compliance.sourceCisSsh')
  if (source === 'puppet') return t('compliance.sourcePuppet')
  return source
}

function KpiCard({ label, value, accent, icon: Icon }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4">
      {Icon && (
        <div className="w-9 h-9 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0">
          <Icon size={18} className="text-gray-400" />
        </div>
      )}
      <div className="min-w-0">
        <div className={`text-[22px] font-semibold leading-none ${accent || 'text-gray-900'}`}>{value}</div>
        <div className="text-[11px] text-gray-400 mt-1 truncate">{label}</div>
      </div>
    </div>
  )
}

// ── Export helpers ────────────────────────────────────────────────────────────

function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function exportFleetJson(nodes) {
  const payload = {
    exported_at: new Date().toISOString(),
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
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json',
    `sabc-fleet-${new Date().toISOString().slice(0, 10)}.json`)
}

function exportFleetCsv(nodes) {
  const rows = [['Node', 'IP', 'OS', 'Score (%)', 'Passed', 'Failed', 'Skipped', 'Source', 'Last Scan']]
  for (const node of nodes) {
    const r = primaryReport(node)
    rows.push([
      node.hostname, node.ip, node.os_family,
      r ? r.score : '', r ? r.passed_checks : '', r ? r.failed_checks : '',
      r ? (r.skipped_checks || 0) : '', r ? r.source : '',
      r ? new Date(r.collected_at).toISOString() : '',
    ])
  }
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadBlob(csv, 'text/csv', `sabc-fleet-${new Date().toISOString().slice(0, 10)}.csv`)
}

function exportFleetPdf(nodes, title) {
  const rows = nodes.map((node) => {
    const r = primaryReport(node)
    const score = r ? r.score : null
    const color = score === null ? '#6b7280' : score >= 90 ? '#16a34a' : score >= 70 ? '#f59e0b' : '#dc2626'
    return `<tr>
      <td><b>${node.hostname}</b><br/><small style="color:#666">${node.ip}</small></td>
      <td><span style="color:${color};font-weight:700">${score !== null ? score + '%' : '—'}</span></td>
      <td>${r ? `<span style="color:#16a34a">${r.passed_checks}✓</span> <span style="color:#dc2626">${r.failed_checks}✗</span>` : '—'}</td>
      <td>${r ? r.source : '—'}</td>
      <td>${r ? new Date(r.collected_at).toLocaleString() : '—'}</td>
    </tr>`
  }).join('')

  const html = `<!DOCTYPE html><html><head><title>${title}</title>
<style>
  body{font-family:sans-serif;font-size:12px;margin:24px}
  h2{margin:0 0 4px}p{color:#666;margin:0 0 16px}
  table{width:100%;border-collapse:collapse}
  th,td{border:1px solid #e5e7eb;padding:6px 10px;text-align:left;vertical-align:top}
  th{background:#f9fafb;font-size:10px;font-weight:600;text-transform:uppercase}
  @media print{body{margin:0}}
</style></head><body>
<h2>${title}</h2><p>Generated: ${new Date().toLocaleString()} · ${nodes.length} node(s)</p>
<table><thead><tr><th>Node</th><th>Score</th><th>Controls</th><th>Source</th><th>Last Scan</th></tr></thead>
<tbody>${rows}</tbody></table></body></html>`

  const win = window.open('', '_blank')
  if (win) { win.document.write(html); win.document.close(); setTimeout(() => win.print(), 400) }
}

// ── Export dropdown ───────────────────────────────────────────────────────────

function ExportMenu({ nodes, t }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  function close() { setOpen(false) }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-600 hover:bg-gray-50"
      >
        <Download size={13} />
        {t('compliance.export')}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={close} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-lg shadow-lg z-20 w-36 py-1 text-[12px]">
            <button onClick={() => { exportFleetJson(nodes); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">
              {t('compliance.exportJson')}
            </button>
            <button onClick={() => { exportFleetCsv(nodes); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">
              {t('compliance.exportCsv')}
            </button>
            <button onClick={() => { exportFleetPdf(nodes, t('compliance.title')); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">
              {t('compliance.exportPdf')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CompliancePage() {
  const t = useT()
  const toast = useToast()
  const { data, loading, refetch } = useApi(getComplianceSummary)
  const [scanningAll, setScanningAll] = useState(false)
  const [scanDone, setScanDone] = useState(0)
  const [scanTotal, setScanTotal] = useState(0)

  const stats = useMemo(() => {
    const nodes = data || []
    const scanned = []
    let passed = 0, failed = 0, skipped = 0, critical = 0, scoreSum = 0
    for (const node of nodes) {
      const r = primaryReport(node)
      if (!r) continue
      scanned.push({ node, report: r })
      passed += r.passed_checks || 0
      failed += r.failed_checks || 0
      skipped += r.skipped_checks || 0
      critical += (r.severity_counts?.high) || 0
      scoreSum += r.score || 0
    }
    const avg = scanned.length ? Math.round(scoreSum / scanned.length) : 0
    return { nodes, scanned, passed, failed, skipped, critical, avg }
  }, [data])

  const distribution = [
    { name: t('compliance.passed'), key: 'pass', value: stats.passed },
    { name: t('compliance.failed'), key: 'fail', value: stats.failed },
    { name: t('compliance.skipped'), key: 'skip', value: stats.skipped },
  ].filter((d) => d.value > 0)

  const scoreBars = stats.scanned
    .map(({ node, report }) => ({ name: node.hostname, score: report.score || 0 }))
    .sort((a, b) => a.score - b.score)
    .slice(0, 12)

  const hasData = stats.scanned.length > 0

  async function scanAll() {
    if (!stats.nodes.length) return
    const nodes = stats.nodes
    setScanningAll(true)
    setScanDone(0)
    setScanTotal(nodes.length)
    try {
      let done = 0
      await Promise.allSettled(nodes.map(async (n) => {
        try { await collectNodeCompliance(n.node_id) } catch { /* ignore individual failure */ }
        done += 1
        setScanDone(done)
      }))
      toast(t('compliance.scanAllDone', { n: done }), 'success')
      await refetch()
    } catch {
      toast(t('compliance.scanAllDone', { n: 0 }), 'error')
    } finally {
      setScanningAll(false)
      setScanDone(0)
      setScanTotal(0)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
            <ShieldCheck size={18} className="text-brand" />
            {t('compliance.title')}
          </h2>
          <p className="text-[13px] text-gray-500 mt-0.5">{t('compliance.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={refetch}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            {t('common.refresh') || 'Refresh'}
          </button>
          <ExportMenu nodes={stats.nodes} t={t} />
          <button
            onClick={scanAll}
            disabled={scanningAll || !stats.nodes.length}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand text-white text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={13} className={scanningAll ? 'animate-pulse' : ''} />
            {scanningAll ? t('compliance.scanningAll') : t('compliance.scanAll')}
          </button>
        </div>
      </div>

      {/* Scan All progress bar */}
      {scanningAll && scanTotal > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-3.5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium text-gray-700">
              {t('compliance.scanningAllProgress', { done: scanDone, total: scanTotal })}
            </span>
            <span className="text-[12px] font-semibold text-brand tabular-nums">
              {Math.round((scanDone / scanTotal) * 100)}%
            </span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${Math.round((scanDone / scanTotal) * 100)}%`,
                background: 'linear-gradient(90deg, #2563eb 0%, #7c3aed 100%)',
              }}
            />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label={t('compliance.avgScore')} value={`${stats.avg}%`} accent={scoreColor(stats.avg)} icon={ShieldCheck} />
        <KpiCard label={t('compliance.nodesScanned')} value={stats.scanned.length} />
        <KpiCard label={t('compliance.totalPassed')} value={stats.passed} accent="text-green-600" />
        <KpiCard label={t('compliance.totalFailed')} value={stats.failed} accent="text-red-600" />
        <KpiCard label={t('compliance.criticalFailures')} value={stats.critical} accent={stats.critical ? 'text-red-600' : 'text-gray-900'} icon={stats.critical ? AlertTriangle : undefined} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-800 mb-3">{t('compliance.controlDistribution')}</h3>
          {hasData && distribution.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={distribution} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={2}>
                  {distribution.map((d) => <Cell key={d.key} fill={C[d.key]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-[12px] text-gray-400">{t('compliance.noChartData')}</div>
          )}
          <div className="flex items-center justify-center gap-4 mt-2">
            {distribution.map((d) => (
              <span key={d.key} className="flex items-center gap-1.5 text-[11px] text-gray-500">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: C[d.key] }} />
                {d.name} <b className="text-gray-700">{d.value}</b>
              </span>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-800 mb-3">{t('compliance.scoreByNode')}</h3>
          {hasData ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={scoreBars} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [`${v}%`, t('compliance.score')]} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={14}>
                  {scoreBars.map((b, i) => (
                    <Cell key={i} fill={b.score >= 90 ? C.pass : b.score >= 70 ? '#f59e0b' : C.fail} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center text-[12px] text-gray-400">{t('compliance.noChartData')}</div>
          )}
        </div>
      </div>

      {/* Fleet table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h3 className="text-[13px] font-semibold text-gray-800">{t('compliance.fleetTitle')}</h3>
        </div>
        {loading && !data ? (
          <div className="p-6 space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-9 bg-gray-100 animate-pulse rounded" />)}
          </div>
        ) : !stats.nodes.length ? (
          <div className="p-8 text-center text-[13px] text-gray-400">{t('compliance.noNodes')}</div>
        ) : (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                <th className="text-left px-5 py-2.5">{t('compliance.node')}</th>
                <th className="text-left px-5 py-2.5 w-48">{t('compliance.score')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.controls')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.source')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.lastScan')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {stats.nodes.map((node) => {
                const r = primaryReport(node)
                return (
                  <tr key={node.node_id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-gray-800">{node.hostname}</div>
                      <div className="text-[11px] text-gray-400">{node.ip}</div>
                    </td>
                    <td className="px-5 py-3">
                      {r ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden max-w-[100px]">
                            <div className={`h-full rounded-full ${scoreBarColor(r.score)}`} style={{ width: `${r.score}%` }} />
                          </div>
                          <span className={`text-[12px] font-semibold ${scoreColor(r.score)}`}>{r.score}%</span>
                        </div>
                      ) : (
                        <span className="text-gray-300">{t('compliance.notScanned')}</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {r ? (
                        <span className="text-[11px] text-gray-500">
                          <b className="text-green-600">{r.passed_checks}</b> · <b className="text-red-600">{r.failed_checks}</b>
                          {r.skipped_checks ? <> · <b className="text-gray-400">{r.skipped_checks}</b></> : null}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-5 py-3">
                      {r ? <span className={badge(r.source === 'scan' ? 'info' : 'gray')}>{sourceLabel(t, r.source)}</span> : '—'}
                    </td>
                    <td className="px-5 py-3 text-gray-400">
                      {r ? new Date(r.collected_at).toLocaleString() : t('compliance.neverScanned')}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link to={`/compliance/${node.node_id}`} className="inline-flex items-center gap-1 text-[12px] text-brand hover:underline">
                        {t('compliance.viewReport')} <ChevronRight size={13} />
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
