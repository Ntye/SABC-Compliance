import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { ShieldCheck, RefreshCw, ChevronRight, AlertTriangle, Download, ChevronDown, Clock, Settings } from 'lucide-react'
import { getComplianceSummary, collectNodeCompliance, getAutoScanSchedule, setAutoScanSchedule, getUserRole } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { badge, scoreColor, scoreBarColor } from '../lib/tw.js'
import { utcDate } from '../lib/time.js'
import RunScanButton from '../components/RunScanButton.jsx'
import ComplianceHistory from '../components/ComplianceHistory.jsx'
import Pagination from '../components/Pagination.jsx'
import { usePagination } from '../hooks/usePagination.js'
import { exportFleetJson, exportFleetCsv, exportFleetPdf } from '../lib/complianceExport.js'

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

// ── Export dropdown (fleet posture) ───────────────────────────────────────────
// Exporters live in ../lib/complianceExport.js so JSON/CSV/PDF share one column
// set and one audit path with the node and history exports.

function ExportMenu({ nodes, t }) {
  const [open, setOpen] = useState(false)
  const meta = { title: t('compliance.title'), filterLabel: null }
  return (
    <div className="relative">
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
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-lg shadow-lg z-20 w-36 py-1 text-[12px]">
            {[['json', exportFleetJson], ['csv', exportFleetCsv], ['pdf', exportFleetPdf]].map(([fmt, fn]) => (
              <button
                key={fmt}
                onClick={() => { fn(nodes, meta); setOpen(false) }}
                className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700"
              >
                {t(`compliance.export${fmt.charAt(0).toUpperCase() + fmt.slice(1)}`)}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── Auto-Scan schedule panel ──────────────────────────────────────────────────

function fmtRelative(isoStr) {
  if (!isoStr) return null
  const diff = utcDate(isoStr) - Date.now()
  const abs = Math.abs(diff)
  if (abs < 60000) return diff < 0 ? 'just now' : 'in a moment'
  const mins = Math.round(abs / 60000)
  if (mins < 60) return diff < 0 ? `${mins}m ago` : `in ${mins}m`
  const hrs = Math.round(abs / 3600000)
  if (hrs < 24) return diff < 0 ? `${hrs}h ago` : `in ${hrs}h`
  return diff < 0 ? `${Math.round(abs / 86400000)}d ago` : `in ${Math.round(abs / 86400000)}d`
}

function AutoScanPanel({ t, toast, getUserRole }) {
  const { data: sched, refetch: refetchSched } = useApi(getAutoScanSchedule)
  const [open,     setOpen]     = useState(false)
  const [saving,   setSaving]   = useState(false)
  const [enabled,  setEnabled]  = useState(true)
  const [interval, setInterval] = useState(30)
  const [unit,     setUnit]     = useState('minutes')
  const isAdmin = getUserRole() === 'admin'

  // Populate form from loaded schedule
  useEffect(() => {
    if (!sched) return
    setEnabled(sched.enabled)
    setInterval(sched.interval ?? 30)
    setUnit(sched.unit || 'minutes')
  }, [sched])

  // Refresh next-run display every minute
  const [, forceRender] = useState(0)
  useEffect(() => {
    const id = setInterval(() => forceRender((n) => n + 1), 60000)
    return () => clearInterval(id)
  }, [])

  async function save() {
    setSaving(true)
    try {
      await setAutoScanSchedule({ enabled, interval: Number(interval), unit })
      await refetchSched()
      toast(t('compliance.scheduleSaved'), 'success')
      setOpen(false)
    } catch (err) {
      toast(err.message || t('compliance.scheduleFailed'), 'error')
    } finally {
      setSaving(false)
    }
  }

  const isEnabled = sched?.enabled ?? true
  const nextRun  = sched?.next_run
  const lastRun  = sched?.last_run

  return (
    <div className="bg-white rounded-xl border border-gray-100 px-4 py-3">
      <div className="flex items-center gap-3">
        <Clock size={15} className="text-gray-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-medium text-gray-700">{t('compliance.autoScan')}</span>
            <span className={`inline-flex items-center px-2 py-[2px] rounded-full text-[10px] font-medium ${isEnabled ? 'bg-green-600/10 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
              {isEnabled ? t('compliance.autoScanOn') : t('compliance.autoScanOff')}
            </span>
            {isEnabled && sched && (
              <span className="text-[11px] text-gray-400">
                {t('compliance.scanEvery')} {sched.interval} {t(`compliance.unit${sched.unit.charAt(0).toUpperCase() + sched.unit.slice(1)}`).toLowerCase()}
              </span>
            )}
          </div>
          {isEnabled && (
            <div className="flex items-center gap-3 mt-0.5">
              {lastRun && (
                <span className="text-[11px] text-gray-400">
                  {t('compliance.lastAutoScan')}: <b className="text-gray-600">{fmtRelative(lastRun)}</b>
                </span>
              )}
              {nextRun && (
                <span className="text-[11px] text-gray-400">
                  {t('compliance.nextAutoScan')}: <b className="text-gray-600">{fmtRelative(nextRun)}</b>
                </span>
              )}
              {!lastRun && (
                <span className="text-[11px] text-gray-400 italic">{t('compliance.neverScannedAuto')}</span>
              )}
            </div>
          )}
        </div>
        {isAdmin && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition flex-shrink-0"
            title="Configure auto-scan schedule"
          >
            <Settings size={14} />
          </button>
        )}
      </div>

      {open && isAdmin && (
        <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-3 flex-wrap">
          {/* Enable toggle */}
          <button
            onClick={() => setEnabled((e) => !e)}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-medium border transition ${
              enabled
                ? 'bg-green-600/10 border-green-600/20 text-green-700 hover:bg-green-600/20'
                : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {enabled ? t('compliance.autoScanOn') : t('compliance.autoScanOff')}
          </button>

          {/* Interval */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-gray-500">{t('compliance.scanEvery')}</span>
            <input
              type="number"
              min="1"
              value={interval}
              onChange={(e) => setInterval(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-16 border border-gray-200 rounded-lg px-2 py-1 text-[12px] text-gray-700 text-center focus:outline-none focus:ring-1 focus:ring-brand/40"
            />
            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1 text-[12px] text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-brand/40"
            >
              <option value="seconds">{t('compliance.unitSeconds')}</option>
              <option value="minutes">{t('compliance.unitMinutes')}</option>
              <option value="days">{t('compliance.unitDays')}</option>
            </select>
          </div>

          <button
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg bg-brand text-white text-[11px] font-medium hover:bg-brand/90 disabled:opacity-50 transition"
          >
            {saving ? t('compliance.savingSchedule') : t('compliance.saveSchedule')}
          </button>
          <button
            onClick={() => setOpen(false)}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-[11px] text-gray-500 hover:bg-gray-50 transition"
          >
            {t('common.cancel') || 'Cancel'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CompliancePage() {
  const t = useT()
  const toast = useToast()
  const { data, loading, refetch } = useApi(getComplianceSummary)
  const [scanningAll,   setScanningAll]  = useState(false)
  const [scanDone,      setScanDone]     = useState(0)
  const [scanTotal,     setScanTotal]    = useState(0)
  const [tab,           setTab]          = useState('posture')  // 'posture' | 'history'

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
  const pager = usePagination(stats.nodes)

  async function scanAll(profileId = null) {
    if (!stats.nodes.length) return
    const nodes = stats.nodes
    setScanningAll(true)
    setScanDone(0)
    setScanTotal(nodes.length)
    try {
      let done = 0
      await Promise.allSettled(nodes.map(async (n) => {
        try { await collectNodeCompliance(n.node_id, profileId) } catch { /* ignore individual failure */ }
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
          {tab === 'posture' && (
            <button
              onClick={refetch}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-600 hover:bg-gray-50"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              {t('common.refresh') || 'Refresh'}
            </button>
          )}
          {tab === 'posture' && <ExportMenu nodes={stats.nodes} t={t} />}
          <RunScanButton
            onRun={scanAll}
            running={scanningAll}
            disabled={!stats.nodes.length}
            label={t('compliance.scanAll')}
            runningLabel={t('compliance.scanningAll')}
            size="sm"
            t={t}
          />
        </div>
      </div>

      {/* Tabs — Compliance posture (primary) + History */}
      <div className="flex items-center gap-1 border-b border-gray-100">
        {[['posture', 'compliance.postureTab'], ['history', 'compliance.historyTab']].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition ${
              tab === key ? 'border-brand text-brand' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t(label)}
          </button>
        ))}
      </div>

      {tab === 'history' ? (
        <ComplianceHistory nodeId={null} />
      ) : (
      <>
      {/* Auto-scan schedule panel */}
      <AutoScanPanel t={t} toast={toast} getUserRole={getUserRole} />

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
          <>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                <th className="text-left px-5 py-2.5">{t('compliance.node')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.tier')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.enforcement')}</th>
                <th className="text-left px-5 py-2.5 w-48">{t('compliance.score')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.controls')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.source')}</th>
                <th className="text-left px-5 py-2.5">{t('compliance.lastScan')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {pager.pageItems.map((node) => {
                const r = primaryReport(node)
                return (
                  <tr key={node.node_id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-3">
                      <div className="font-medium text-gray-800">{node.hostname}</div>
                      <div className="text-[11px] text-gray-400">{node.ip}</div>
                    </td>
                    <td className="px-5 py-3">
                      {node.tier_name
                        ? <span className={badge('gray')}>{node.tier_name}</span>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-3">
                      <span className={badge(node.enforce ? 'success' : 'gray')}>
                        {node.enforce ? t('compliance.enforceOn') : t('compliance.enforceOff')}
                      </span>
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
                      {r ? utcDate(r.collected_at).toLocaleString() : t('compliance.neverScanned')}
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
          <Pagination {...pager} />
          </>
        )}
      </div>
      </>
      )}
    </div>
  )
}
