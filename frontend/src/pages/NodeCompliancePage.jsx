import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts'
import {
  ArrowLeft, Play, Wrench, CheckCircle2, XCircle, MinusCircle, ChevronDown,
  Download, ShieldAlert,
} from 'lucide-react'
import {
  getNodeCompliance, collectNodeCompliance, triggerRemediation,
  getInspecStatus, installInspecOnController,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { badge, scoreColor, scoreBarColor } from '../lib/tw.js'

// ── Export helpers ────────────────────────────────────────────────────────────

function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function exportNodeJson(data, report) {
  const payload = {
    exported_at: new Date().toISOString(),
    node: { hostname: data.hostname, ip: data.ip, os_family: data.os_family },
    report: {
      score: report.score, passed_checks: report.passed_checks,
      failed_checks: report.failed_checks, skipped_checks: report.skipped_checks,
      source: report.source, collected_at: report.collected_at, profile: report.profile,
      controls: report.details || [],
    },
  }
  downloadBlob(JSON.stringify(payload, null, 2), 'application/json',
    `sabc-scan-${data.hostname}-${new Date().toISOString().slice(0, 10)}.json`)
}

function exportNodeCsv(data, report) {
  const rows = [['Control ID', 'Title', 'Status', 'Severity', 'Section', 'Description', 'Failure Detail']]
  for (const ctrl of (report.details || [])) {
    rows.push([ctrl.control_id, ctrl.title, ctrl.status, ctrl.severity || '',
      ctrl.section || '', ctrl.desc || '', ctrl.message || ''])
  }
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  downloadBlob(csv, 'text/csv',
    `sabc-scan-${data.hostname}-${new Date().toISOString().slice(0, 10)}.csv`)
}

function exportNodePdf(data, report) {
  const rows = (report.details || []).map((ctrl) => {
    const color = ctrl.status === 'fail' ? '#dc2626' : ctrl.status === 'pass' ? '#16a34a' : '#6b7280'
    const bg = ctrl.status === 'fail' ? '#fff5f5' : ''
    return `<tr style="background:${bg}">
      <td>${ctrl.control_id}</td>
      <td>${ctrl.title}</td>
      <td style="color:${color};font-weight:600">${ctrl.status}</td>
      <td>${ctrl.severity || ''}</td>
      <td>${ctrl.section || ''}</td>
    </tr>`
  }).join('')
  const scoreColor = report.score >= 90 ? '#16a34a' : report.score >= 70 ? '#f59e0b' : '#dc2626'
  const html = `<!DOCTYPE html><html><head><title>SABC — ${data.hostname}</title>
<style>
  body{font-family:sans-serif;font-size:11px;margin:24px}
  h2{margin:0 0 4px}.meta{color:#555;margin-bottom:16px}
  .score{font-size:22px;font-weight:700;color:${scoreColor}}
  table{width:100%;border-collapse:collapse;margin-top:12px}
  th,td{border:1px solid #e5e7eb;padding:5px 8px;text-align:left;vertical-align:top}
  th{background:#f9fafb;font-size:10px;font-weight:600;text-transform:uppercase}
  @media print{body{margin:0}}
</style></head><body>
<h2>SABC Compliance Report — ${data.hostname}</h2>
<div class="meta">
  IP: ${data.ip} · OS: ${data.os_family} ·
  Score: <span class="score">${report.score}%</span> ·
  ${report.passed_checks} passed · ${report.failed_checks} failed ·
  Scanned: ${new Date(report.collected_at).toLocaleString()}
</div>
<table><thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Severity</th><th>Section</th></tr></thead>
<tbody>${rows}</tbody></table></body></html>`
  const win = window.open('', '_blank')
  if (win) { win.document.write(html); win.document.close(); setTimeout(() => win.print(), 400) }
}

function ExportMenu({ nodeData, report, t }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  function close() { setOpen(false) }
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-gray-200 text-gray-700 text-[13px] font-medium hover:bg-gray-50"
      >
        <Download size={14} />
        {t('compliance.export')}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={close} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-lg shadow-lg z-20 w-36 py-1 text-[12px]">
            <button onClick={() => { exportNodeJson(nodeData, report); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">{t('compliance.exportJson')}</button>
            <button onClick={() => { exportNodeCsv(nodeData, report); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">{t('compliance.exportCsv')}</button>
            <button onClick={() => { exportNodePdf(nodeData, report); close() }} className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700">{t('compliance.exportPdf')}</button>
          </div>
        </>
      )}
    </div>
  )
}

const C = { pass: '#16a34a', fail: '#dc2626', skip: '#9ca3af' }
const SEV = { high: '#dc2626', medium: '#f59e0b', low: '#3b82f6', info: '#9ca3af' }
const SEV_W = { high: 0, medium: 1, low: 2, info: 3 }

const CIS_SECTIONS = {
  1: 'Initial Setup', 2: 'Services', 3: 'Network Configuration',
  4: 'Logging & Auditing', 5: 'Access, Authentication & Authorization',
  6: 'System Maintenance',
}

const FRAMEWORKS = [
  { key: 'all', label: 'All' },
  { key: 'cis', label: 'CIS' },
]

function sectionOf(ctrl) {
  if (ctrl.section) return ctrl.section
  const cis = ctrl.frameworks?.cis || (/^\d/.test(ctrl.control_id || '') ? ctrl.control_id : '')
  const top = String(cis).split('.')[0]
  return CIS_SECTIONS[top] ? `${top} · ${CIS_SECTIONS[top]}` : 'Other'
}

function numParts(cid) {
  return (cid || '').split('.').filter((p) => /^\d+$/.test(p))
}

function ctrlCounts(controls) {
  let passed = 0, failed = 0
  for (const c of controls) {
    if (c.status === 'pass') passed++
    else if (c.status === 'fail') failed++
  }
  return { passed, failed, total: controls.length }
}

function mergeCounts(...cs) {
  return cs.reduce(
    (a, c) => ({ passed: a.passed + c.passed, failed: a.failed + c.failed, total: a.total + c.total }),
    { passed: 0, failed: 0, total: 0 },
  )
}

// Build a 3-level hierarchy from compliance controls using their numeric control_id parts.
// Level 1 (TopGroup)  : sectionOf(ctrl)  e.g. "1 · Initial Setup"
// Level 2 (Section)   : first 2 numeric parts  e.g. "1.1"
// Level 3 (Subsection): first 3 numeric parts  e.g. "1.1.1"
// Controls sit inside subsections.  Any level whose key is '__flat' renders without a header.
function buildComplianceTree(controls) {
  const byStatus = (a, b) => {
    const sa = a.status === 'fail' ? 0 : a.status === 'skip' ? 2 : 1
    const sb = b.status === 'fail' ? 0 : b.status === 'skip' ? 2 : 1
    return sa !== sb ? sa - sb : (SEV_W[a.severity] ?? 9) - (SEV_W[b.severity] ?? 9)
  }

  const sorted = [...controls].sort((a, b) => {
    const ap = numParts(a.control_id), bp = numParts(b.control_id)
    for (let i = 0; i < Math.max(ap.length, bp.length); i++) {
      const d = parseInt(ap[i] ?? '0') - parseInt(bp[i] ?? '0')
      if (d) return d
    }
    return (a.control_id || '').localeCompare(b.control_id || '')
  })

  function numSort(items) {
    return [...items].sort((a, b) => {
      if (a.key === '__flat') return -1
      if (b.key === '__flat') return 1
      const ak = a.key.split('.').map(Number)
      const bk = b.key.split('.').map(Number)
      for (let i = 0; i < Math.max(ak.length, bk.length); i++) {
        const d = (ak[i] || 0) - (bk[i] || 0)
        if (d) return d
      }
      return 0
    })
  }

  const topMap = new Map()

  for (const ctrl of sorted) {
    const topName = sectionOf(ctrl)
    if (!topMap.has(topName)) topMap.set(topName, { name: topName, secMap: new Map() })
    const top = topMap.get(topName)

    const parts = numParts(ctrl.control_id)
    const secKey = parts.length >= 3 ? parts.slice(0, 2).join('.') : '__flat'
    if (!top.secMap.has(secKey))
      top.secMap.set(secKey, { key: secKey, label: secKey === '__flat' ? '' : secKey, ssMap: new Map() })
    const sec = top.secMap.get(secKey)

    const ssKey = parts.length >= 4 ? parts.slice(0, 3).join('.') : '__flat'
    if (!sec.ssMap.has(ssKey))
      sec.ssMap.set(ssKey, { key: ssKey, label: ssKey === '__flat' ? '' : ssKey, controls: [] })
    sec.ssMap.get(ssKey).controls.push(ctrl)
  }

  const groups = []
  for (const [, top] of topMap) {
    groups.push({
      name: top.name,
      sections: numSort([...top.secMap.values()]).map((sec) => ({
        ...sec,
        subsections: numSort([...sec.ssMap.values()]).map((ss) => ({
          ...ss,
          controls: [...ss.controls].sort(byStatus),
        })),
      })),
    })
  }

  groups.sort((a, b) => (parseInt(a.name) || 999) - (parseInt(b.name) || 999))
  return groups
}

function primaryReport(reports) {
  return (
    reports.find((r) => r.source === 'inspec') ||
    reports.find((r) => r.source === 'cis-ssh') ||
    reports.find((r) => r.source !== 'puppet') ||
    null
  )
}

function StatusIcon({ status }) {
  if (status === 'pass') return <CheckCircle2 size={15} className="text-green-500 flex-shrink-0" />
  if (status === 'fail') return <XCircle size={15} className="text-red-500 flex-shrink-0" />
  return <MinusCircle size={15} className="text-gray-300 flex-shrink-0" />
}

function ControlRow({ ctrl, t }) {
  const [open, setOpen] = useState(false)
  const fw = ctrl.frameworks || {}
  const fwKeys = Object.keys(fw)
  const sev = ctrl.severity || 'info'
  return (
    <div className="border-b border-gray-50 last:border-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-3 hover:bg-gray-50/50 text-left"
      >
        <StatusIcon status={ctrl.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-[11px] text-gray-400">{ctrl.control_id}</span>
            <span className="text-[12px] text-gray-800 font-medium">{ctrl.title}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {fwKeys.map((k) => (
            <span key={k} className={badge(k === 'pci_dss' ? 'pci-dss' : k)}>
              {k === 'pci_dss' ? 'PCI' : k.toUpperCase()} {fw[k]}
            </span>
          ))}
          {ctrl.severity && (
            <span
              className="inline-flex items-center px-2 py-[3px] rounded-full text-[10px] font-medium"
              style={{ background: `${SEV[sev]}22`, color: SEV[sev] }}
            >
              {t(`compliance.${sev}`)}
            </span>
          )}
          <ChevronDown size={14} className={`text-gray-300 transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {open && (
        <div className="px-5 pb-3 pl-[42px] space-y-1.5">
          {ctrl.desc && <p className="text-[12px] text-gray-500">{ctrl.desc}</p>}
          {ctrl.message && (
            <pre className="text-[11px] text-gray-600 bg-gray-50 border border-gray-100 rounded-md p-2 whitespace-pre-wrap font-mono">
              {ctrl.message}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function Panel({ title, children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-100 p-5 ${className}`}>
      <h3 className="text-[13px] font-semibold text-gray-800 mb-3">{title}</h3>
      {children}
    </div>
  )
}

// Level 3: sub-subsection (e.g. "1.1.1") — __flat renders controls directly
function ComplianceSubsection({ ss, t }) {
  const [open, setOpen] = useState(true)

  if (ss.key === '__flat') {
    return <>{ss.controls.map((c) => <ControlRow key={c.control_id} ctrl={c} t={t} />)}</>
  }

  const { passed, failed, total } = ctrlCounts(ss.controls)
  const scored = passed + failed
  const pct = scored ? Math.round((passed / scored) * 100) : 0

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 pl-9 pr-5 py-2 hover:bg-gray-50/30 text-left"
      >
        <ChevronDown
          size={12}
          className={`text-gray-300 flex-shrink-0 transition-transform ${open ? '' : '-rotate-90'}`}
        />
        <span className="text-[10px] font-mono font-semibold text-brand/50 w-12 flex-shrink-0">{ss.label}</span>
        <span className="flex-1" />
        {failed > 0 && <span className="text-[11px] text-red-500 font-medium mr-1.5">{failed}✗</span>}
        <div className="w-12 h-1.5 rounded-full bg-gray-200 overflow-hidden">
          <div className={`h-full rounded-full ${scoreBarColor(pct)}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[10px] text-gray-400 tabular-nums w-10 text-right">{passed}/{scored || total}</span>
      </button>
      {open && ss.controls.map((c) => <ControlRow key={c.control_id} ctrl={c} t={t} />)}
    </div>
  )
}

// Level 2: sub-section (e.g. "1.1") — __flat renders subsections directly
function ComplianceSection({ sec, t }) {
  const [open, setOpen] = useState(true)

  if (sec.key === '__flat') {
    return <>{sec.subsections.map((ss) => <ComplianceSubsection key={ss.key} ss={ss} t={t} />)}</>
  }

  const counts = mergeCounts(...sec.subsections.map((ss) => ctrlCounts(ss.controls)))
  const { passed, failed, total } = counts
  const scored = passed + failed
  const pct = scored ? Math.round((passed / scored) * 100) : 0

  return (
    <div className="border-b border-gray-50 last:border-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 pl-6 pr-5 py-2.5 bg-white/80 hover:bg-gray-50/30 text-left"
      >
        <ChevronDown
          size={13}
          className={`text-gray-400 flex-shrink-0 transition-transform ${open ? '' : '-rotate-90'}`}
        />
        <span className="text-[11px] font-mono font-semibold text-gray-500 w-14 flex-shrink-0">{sec.label}</span>
        <span className="flex-1" />
        {failed > 0 && <span className="text-[11px] text-red-500 font-medium mr-2">{failed} failed</span>}
        <div className="w-14 h-1.5 rounded-full bg-gray-200 overflow-hidden">
          <div className={`h-full rounded-full ${scoreBarColor(pct)}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] text-gray-400 tabular-nums w-10 text-right">{passed}/{scored || total}</span>
      </button>
      {open && sec.subsections.map((ss) => <ComplianceSubsection key={ss.key} ss={ss} t={t} />)}
    </div>
  )
}

// Level 1: top section group (e.g. "1 · Initial Setup")
function ComplianceTopGroup({ group, t }) {
  const [open, setOpen] = useState(true)
  const counts = mergeCounts(
    ...group.sections.map((sec) => mergeCounts(...sec.subsections.map((ss) => ctrlCounts(ss.controls)))),
  )
  const { passed, failed, total } = counts
  const scored = passed + failed
  const pct = scored ? Math.round((passed / scored) * 100) : 0

  return (
    <div className="border-b border-gray-100 last:border-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-3 bg-gray-50/60 hover:bg-gray-50 text-left"
      >
        <ChevronDown size={15} className={`text-gray-400 transition-transform ${open ? '' : '-rotate-90'}`} />
        <span className="text-[12px] font-semibold text-gray-700 flex-1">{group.name}</span>
        {failed > 0 && (
          <span className="text-[11px] text-red-500 font-medium">{failed} {t('compliance.failed').toLowerCase()}</span>
        )}
        <div className="w-20 h-1.5 rounded-full bg-gray-200 overflow-hidden">
          <div className={`h-full rounded-full ${scoreBarColor(pct)}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] text-gray-400 tabular-nums w-12 text-right">{passed}/{scored || total}</span>
      </button>
      {open && group.sections.map((sec) => <ComplianceSection key={sec.key} sec={sec} t={t} />)}
    </div>
  )
}

export default function NodeCompliancePage() {
  const { id } = useParams()
  const t = useT()
  const toast = useToast()
  const { data, loading, refetch } = useApi(() => getNodeCompliance(id), { deps: [id] })
  const { data: inspecStatus, refetch: refetchInspec } = useApi(getInspecStatus)
  const [scanning,    setScanning]    = useState(false)
  const [scanPct,     setScanPct]     = useState(0)
  const scanStartRef = useRef(null)
  const scanTimerRef = useRef(null)

  useEffect(() => {
    if (scanning) {
      scanStartRef.current = Date.now()
      setScanPct(0)
      scanTimerRef.current = setInterval(() => {
        const elapsed = Date.now() - scanStartRef.current
        // Asymptotic: quickly reaches ~60%, slows toward 99%
        setScanPct(Math.min(99, Math.round(99 * (1 - Math.exp(-elapsed / 22000)))))
      }, 250)
    } else {
      clearInterval(scanTimerRef.current)
      if (scanStartRef.current !== null) {
        setScanPct(100)
        setTimeout(() => { setScanPct(0); scanStartRef.current = null }, 900)
      }
    }
    return () => clearInterval(scanTimerRef.current)
  }, [scanning])
  const [installing, setInstalling] = useState(false)
  const [remediating, setRemediating] = useState(false)
  const [filter, setFilter] = useState('all')
  const [fwFilter, setFwFilter] = useState('all')

  const inspecInstalled = inspecStatus?.installed
  const report = useMemo(() => (data ? primaryReport(data.reports || []) : null), [data])

  const history = useMemo(() => {
    if (!data) return []
    return (data.reports || [])
      .filter((r) => r.source === 'inspec' || r.source === 'cis-ssh')
      .map((r) => ({
        ts: new Date(r.collected_at).getTime(),
        date: new Date(r.collected_at).toLocaleDateString(),
        score: r.score,
      }))
      .sort((a, b) => a.ts - b.ts)
  }, [data])

  const severityBars = useMemo(() => {
    const sc = report?.severity_counts || {}
    return [
      { name: t('compliance.high'), key: 'high', value: sc.high || 0 },
      { name: t('compliance.medium'), key: 'medium', value: sc.medium || 0 },
      { name: t('compliance.low'), key: 'low', value: sc.low || 0 },
      { name: t('compliance.info'), key: 'info', value: sc.info || 0 },
    ]
  }, [report, t])

  const distribution = useMemo(() => {
    if (!report) return []
    return [
      { name: t('compliance.passed'), key: 'pass', value: report.passed_checks },
      { name: t('compliance.failed'), key: 'fail', value: report.failed_checks },
      { name: t('compliance.skipped'), key: 'skip', value: report.skipped_checks || 0 },
    ].filter((d) => d.value > 0)
  }, [report, t])

  const complianceTree = useMemo(() => {
    let details = report?.details || []
    if (filter === 'failed') details = details.filter((d) => d.status === 'fail')
    else if (filter === 'passed') details = details.filter((d) => d.status === 'pass')
    if (fwFilter !== 'all') details = details.filter((d) => (d.frameworks || {})[fwFilter])
    return buildComplianceTree(details)
  }, [report, filter, fwFilter])

  const totalShown = useMemo(
    () =>
      complianceTree.reduce(
        (n, g) => n + g.sections.reduce((m, s) => m + s.subsections.reduce((k, ss) => k + ss.controls.length, 0), 0),
        0,
      ),
    [complianceTree],
  )

  async function runScan() {
    setScanning(true)
    try {
      const res = await collectNodeCompliance(id)
      toast(t('compliance.scanned', { n: res.collected?.length || 0 }), 'success')
      await Promise.all([refetch(), refetchInspec()])
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setScanning(false)
    }
  }

  async function installInspec() {
    setInstalling(true)
    try {
      const res = await installInspecOnController()
      if (res.installed || res.success) {
        toast(t('compliance.inspecInstalled'), 'success')
        await refetchInspec()
      } else {
        toast(res.error || 'InSpec installation failed', 'error')
      }
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setInstalling(false)
    }
  }

  async function remediate() {
    setRemediating(true)
    try {
      await triggerRemediation(id)
      toast(t('compliance.remediated'), 'success')
      await refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRemediating(false)
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link to="/compliance" className="inline-flex items-center gap-1 text-[12px] text-gray-400 hover:text-gray-600 mb-1">
            <ArrowLeft size={13} /> {t('compliance.backToFleet')}
          </Link>
          <h2 className="text-[18px] font-semibold text-gray-900">{data?.hostname || id}</h2>
          {data && <p className="text-[12px] text-gray-400">{data.ip} · {data.os_family}</p>}
        </div>
        <div className="flex items-center gap-2">
          {report && data && <ExportMenu nodeData={data} report={report} t={t} />}
          <button
            onClick={runScan}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={14} className={scanning ? 'animate-pulse' : ''} />
            {scanning ? t('compliance.scanning') : t('compliance.runScan')}
          </button>
          <button
            onClick={remediate}
            disabled={remediating || !data?.puppet_enrolled}
            title={!data?.puppet_enrolled ? t('compliance.puppetFirst') : ''}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 text-gray-700 text-[13px] font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Wrench size={14} />
            {remediating ? t('compliance.remediating') : t('compliance.remediate')}
          </button>
        </div>
      </div>

      {/* Scan progress bar */}
      {(scanning || scanPct > 0) && (
        <div className="bg-white rounded-xl border border-gray-100 px-5 py-3.5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium text-gray-700">
              {scanning ? t('compliance.scanInProgress') : t('compliance.scanComplete')}
            </span>
            <span className="text-[12px] font-semibold text-brand tabular-nums">{scanPct}%</span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${scanPct}%`,
                background: scanPct === 100
                  ? '#16a34a'
                  : 'linear-gradient(90deg, #2563eb 0%, #7c3aed 100%)',
              }}
            />
          </div>
        </div>
      )}

      {/* InSpec not installed on the platform — offer to install it right here */}
      {inspecStatus && !inspecInstalled && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 flex items-start gap-3">
          <ShieldAlert size={17} className="text-blue-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-[12px] font-medium text-blue-900">{t('compliance.inspecMissingTitle')}</p>
            <p className="text-[11px] text-blue-700 mt-0.5">{t('compliance.inspecMissingDesc')}</p>
          </div>
          <button
            onClick={installInspec}
            disabled={installing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-[12px] font-medium hover:bg-blue-700 disabled:opacity-50 flex-shrink-0"
          >
            <Download size={13} className={installing ? 'animate-pulse' : ''} />
            {installing ? t('compliance.installing') : t('compliance.installInspec')}
          </button>
        </div>
      )}

      {loading && !data ? (
        <div className="space-y-3">
          {[1, 2].map((i) => <div key={i} className="h-32 bg-gray-100 animate-pulse rounded-xl" />)}
        </div>
      ) : !report ? (
        <div className="bg-white rounded-xl border border-gray-100 p-10 text-center">
          <p className="text-[14px] font-medium text-gray-700">{t('compliance.noReports')}</p>
          <p className="text-[12px] text-gray-400 mt-1">{t('compliance.noReportsDesc')}</p>
        </div>
      ) : (
        <>
          {/* Top row: score donut + breakdown + severity */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Panel title={t('compliance.overallScore')}>
              <div className="relative">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={distribution} dataKey="value" nameKey="name" innerRadius={62} outerRadius={88} paddingAngle={2}>
                      {distribution.map((d) => <Cell key={d.key} fill={C[d.key]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className={`text-[30px] font-bold leading-none ${scoreColor(report.score)}`}>{report.score}%</span>
                  <span className="text-[10px] text-gray-400 mt-1">
                    {report.passed_checks}/{report.total_checks} {t('compliance.passed').toLowerCase()}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-center gap-3 mt-1">
                {distribution.map((d) => (
                  <span key={d.key} className="flex items-center gap-1 text-[11px] text-gray-500">
                    <span className="w-2 h-2 rounded-full" style={{ background: C[d.key] }} />{d.name} {d.value}
                  </span>
                ))}
              </div>
            </Panel>

            <Panel title={t('compliance.severityBreakdown')}>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={severityBars} margin={{ left: -16, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={34}>
                    {severityBars.map((b) => <Cell key={b.key} fill={SEV[b.key]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title={t('compliance.scoreHistory')}>
              {history.length > 1 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={history} margin={{ left: -16, right: 8 }}>
                    <CartesianGrid vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <Tooltip formatter={(v) => [`${v}%`, t('compliance.score')]} />
                    <Line type="monotone" dataKey="score" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[200px] flex flex-col items-center justify-center gap-2 text-center">
                  <span className={`text-[40px] font-bold leading-none ${scoreColor(report.score)}`}>{report.score}%</span>
                  <span className="text-[11px] text-gray-400">{t('compliance.noChartData')}</span>
                </div>
              )}
            </Panel>
          </div>

          {/* Report meta */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[11px] text-gray-400 px-1">
            {report.profile && <span>{t('compliance.profile')}: <b className="text-gray-600">{report.profile}</b></span>}
            {report.duration != null && <span>{t('compliance.duration')}: <b className="text-gray-600">{report.duration.toFixed(1)}s</b></span>}
            <span>{t('compliance.collectedAt')}: <b className="text-gray-600">{new Date(report.collected_at).toLocaleString()}</b></span>
            <span>{t('compliance.source')}: <b className="text-gray-600">{report.source}</b></span>
          </div>

          {/* Controls — nested tree by CIS section hierarchy */}
          <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-3 flex-wrap">
              <h3 className="text-[13px] font-semibold text-gray-800">
                {t('compliance.controlsTitle')}
                <span className="ml-2 text-[11px] font-normal text-gray-400">{totalShown}</span>
              </h3>
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
                  {FRAMEWORKS.map((f) => (
                    <button
                      key={f.key}
                      onClick={() => setFwFilter(f.key)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${fwFilter === f.key ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      {f.key === 'all' ? t('compliance.filterAll') : f.label}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
                  {['all', 'failed', 'passed'].map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${filter === f ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                      {t(`compliance.filter${f.charAt(0).toUpperCase() + f.slice(1)}`)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            {complianceTree.length ? (
              complianceTree.map((group) => (
                <ComplianceTopGroup key={group.name} group={group} t={t} />
              ))
            ) : (
              <div className="p-8 text-center text-[12px] text-gray-400">{t('compliance.noControls')}</div>
            )}
          </div>

          {/* Remediation history */}
          {data.remediations?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <h3 className="text-[13px] font-semibold text-gray-800">{t('compliance.remediationHistory')}</h3>
              </div>
              <div className="divide-y divide-gray-50">
                {data.remediations.map((rm) => (
                  <div key={rm.id} className="px-5 py-3 flex items-center justify-between text-[12px]">
                    <div className="flex items-center gap-2">
                      <span className={badge(rm.outcome === 'success' ? 'success' : rm.outcome === 'failed' ? 'danger' : 'gray')}>{rm.outcome}</span>
                      <span className="text-gray-500">{t('compliance.resourcesFixed', { n: rm.resources_fixed })}</span>
                    </div>
                    <span className="text-gray-400">{new Date(rm.triggered_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
