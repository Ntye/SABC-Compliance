import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import { Search, Download, X, Clock, ChevronRight } from 'lucide-react'
import { getComplianceHistory, getComplianceReport } from '../lib/api.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { utcDate } from '../lib/time.js'
import { scoreColor, scoreBarColor } from '../lib/tw.js'
import {
  exportHistoryJson, exportHistoryCsv, exportHistoryPdf,
  exportControlsJson, exportControlsCsv, exportControlsPdf,
} from '../lib/complianceExport.js'

const GRANS = [
  ['minute', 'compliance.byMinute'],
  ['hour', 'compliance.byHour'],
  ['day', 'compliance.byDay'],
  ['month', 'compliance.byMonth'],
  ['year', 'compliance.byYear'],
]

const p2 = (n) => String(n).padStart(2, '0')
const tsOf = (r) => { const d = utcDate(r.collected_at); return d && !isNaN(d) ? d.getTime() : 0 }

// Convert a local `datetime-local` value to a UTC ISO bound (seconds precision,
// no zone suffix) so it compares lexicographically against the stored
// collected_at, which the backend keeps as UTC text.
function toIso(local) {
  if (!local) return null
  const d = new Date(local)
  return isNaN(d) ? null : d.toISOString().slice(0, 19)
}

function bucketKey(d, gran) {
  const base = `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`
  switch (gran) {
    case 'minute': return `${base}T${p2(d.getHours())}:${p2(d.getMinutes())}`
    case 'hour':   return `${base}T${p2(d.getHours())}`
    case 'month':  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`
    case 'year':   return `${d.getFullYear()}`
    default:       return base
  }
}

function bucketLabel(d, gran) {
  const mon = d.toLocaleString(undefined, { month: 'short' })
  switch (gran) {
    case 'minute': return `${mon} ${d.getDate()} ${p2(d.getHours())}:${p2(d.getMinutes())}`
    case 'hour':   return `${mon} ${d.getDate()} ${p2(d.getHours())}:00`
    case 'month':  return `${mon} ${d.getFullYear()}`
    case 'year':   return `${d.getFullYear()}`
    default:       return `${mon} ${d.getDate()}`
  }
}

function aggregate(rows, gran) {
  const m = new Map()
  for (const r of rows) {
    const d = utcDate(r.collected_at)
    if (!d || isNaN(d)) continue
    const key = bucketKey(d, gran)
    const e = m.get(key)
    if (e) {
      e.sum += r.score || 0; e.n += 1
      if (d.getTime() < e.ts) { e.ts = d.getTime(); e.label = bucketLabel(d, gran) }
    } else {
      m.set(key, { key, sum: r.score || 0, n: 1, ts: d.getTime(), label: bucketLabel(d, gran) })
    }
  }
  return [...m.values()]
    .sort((a, b) => a.ts - b.ts)
    .map((e) => ({ label: e.label, score: Math.round(e.sum / e.n), scans: e.n }))
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{label}</span>
      {children}
    </label>
  )
}

function ChartTooltip({ active, payload, t }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white border border-gray-100 rounded-lg shadow-md px-3 py-2 text-[11px]">
      <div className="font-medium text-gray-700">{d.label}</div>
      <div className={scoreColor(d.score)}>{d.score}% {t('compliance.score').toLowerCase()}</div>
      <div className="text-gray-400">{t('compliance.scansCount', { n: d.scans })}</div>
    </div>
  )
}

// Full-report card: appears when a scan is selected from search or the table.
// Exports go through the shared control exporters (same columns as posture).
function ReportCard({ report, nodeId, onClose, t }) {
  const meta = {
    hostname: report.hostname, ip: report.ip, os_family: report.os_family,
    score: report.score, passed_checks: report.passed_checks, failed_checks: report.failed_checks,
    skipped_checks: report.skipped_checks, total_checks: report.total_checks,
    source: report.source, profile: report.profile, collected_at: report.collected_at,
    resourceType: 'node', resourceId: nodeId || report.node_id, resourceName: report.hostname,
    filterLabel: null,
  }
  const controls = report.details || []
  return (
    <div className="bg-white rounded-xl border border-brand/30 ring-1 ring-brand/10 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-3 bg-brand/5">
        <div className="flex items-center gap-3 min-w-0">
          <span className={`text-[20px] font-bold leading-none ${scoreColor(report.score)}`}>{report.score}%</span>
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-gray-800 truncate">{report.hostname}</div>
            <div className="text-[11px] text-gray-400">
              {t('compliance.collectedAt')}: {utcDate(report.collected_at)?.toLocaleString()}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[11px] text-gray-500">
            <b className="text-green-600">{report.passed_checks}</b> · <b className="text-red-600">{report.failed_checks}</b>
            {report.skipped_checks ? <> · <b className="text-gray-400">{report.skipped_checks}</b></> : null}
          </span>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 text-gray-400"><X size={15} /></button>
        </div>
      </div>
      <div className="px-5 py-3 flex items-center gap-2 flex-wrap">
        <span className="text-[11px] text-gray-500 mr-1">{t('compliance.exportThisScan')}:</span>
        {[['json', exportControlsJson], ['csv', exportControlsCsv], ['pdf', exportControlsPdf]].map(([fmt, fn]) => (
          <button
            key={fmt}
            onClick={() => fn(controls, meta)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-600 hover:bg-gray-50"
          >
            <Download size={12} />{t(`compliance.export${fmt.charAt(0).toUpperCase() + fmt.slice(1)}`)}
          </button>
        ))}
        <span className="text-[11px] text-gray-400 ml-auto">{controls.length} {t('compliance.controls').toLowerCase()}</span>
      </div>
    </div>
  )
}

export default function ComplianceHistory({ nodeId = null, nodeName = null }) {
  const t = useT()
  const toast = useToast()
  const [gran,   setGran]   = useState('day')
  const [from,   setFrom]   = useState('')
  const [to,     setTo]     = useState('')
  const [rows,   setRows]   = useState([])
  const [loading, setLoading] = useState(true)
  const [expFmt, setExpFmt] = useState('csv')
  const [searchAt, setSearchAt] = useState('')
  const [report, setReport] = useState(null)
  const [loadingId, setLoadingId] = useState(null)

  const fetchHistory = useCallback(async (f, tRange) => {
    setLoading(true)
    try {
      const data = await getComplianceHistory({ nodeId, from: toIso(f), to: toIso(tRange), limit: 2000 })
      setRows(Array.isArray(data) ? data : [])
    } catch (err) {
      toast(err.message, 'error')
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [nodeId, toast])

  useEffect(() => { fetchHistory('', '') }, [fetchHistory])

  const buckets = useMemo(() => aggregate(rows, gran), [rows, gran])
  const sortedRows = useMemo(() => [...rows].sort((a, b) => tsOf(b) - tsOf(a)), [rows])

  const nearest = useMemo(() => {
    if (!searchAt) return []
    const target = new Date(searchAt).getTime()
    if (isNaN(target)) return []
    return [...rows]
      .map((r) => ({ r, dt: Math.abs(tsOf(r) - target) }))
      .sort((a, b) => a.dt - b.dt)
      .slice(0, 6)
      .map((x) => x.r)
  }, [rows, searchAt])

  async function openReport(r) {
    setLoadingId(r.id)
    try {
      const rep = await getComplianceReport(r.id)
      setReport(rep)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLoadingId(null)
    }
  }

  function exportInterval() {
    if (!rows.length) { toast(t('compliance.noScansRange'), 'error'); return }
    const meta = {
      nodeId,
      label: nodeName || (nodeId || 'Fleet'),
      from: toIso(from),
      to: toIso(to),
    }
    if (expFmt === 'json') exportHistoryJson(rows, meta)
    else if (expFmt === 'pdf') exportHistoryPdf(rows, meta)
    else exportHistoryCsv(rows, meta)
  }

  const rangeActive = Boolean(from || to)
  const shownRows = sortedRows.slice(0, 150)

  return (
    <div className="space-y-4">
      {/* Working window + granularity */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 flex flex-wrap items-end gap-3">
        <Field label={t('compliance.intervalFrom')}>
          <input
            type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand/40"
          />
        </Field>
        <Field label={t('compliance.intervalTo')}>
          <input
            type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand/40"
          />
        </Field>
        <button
          onClick={() => fetchHistory(from, to)}
          className="px-3.5 py-1.5 rounded-lg bg-brand text-white text-[12px] font-medium hover:bg-brand/90"
        >
          {t('compliance.applyInterval')}
        </button>
        {rangeActive && (
          <button
            onClick={() => { setFrom(''); setTo(''); fetchHistory('', '') }}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-500 hover:bg-gray-50"
          >
            {t('compliance.clearRange')}
          </button>
        )}
        <div className="flex-1" />
        <Field label={t('compliance.granularity')}>
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
            {GRANS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => setGran(key)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${gran === key ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              >
                {t(label)}
              </button>
            ))}
          </div>
        </Field>
      </div>

      {/* Score-over-time chart */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-semibold text-gray-800">{t('compliance.historyHeading')}</h3>
          <span className="text-[11px] text-gray-400">{t('compliance.scansCount', { n: rows.length })}</span>
        </div>
        {loading ? (
          <div className="h-[260px] bg-gray-50 animate-pulse rounded-lg" />
        ) : buckets.length ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={buckets} margin={{ left: -14, right: 12, top: 6 }}>
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8' }} interval="preserveStartEnd" minTickGap={24} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <Tooltip content={<ChartTooltip t={t} />} />
              <Line type="monotone" dataKey="score" stroke="#2563eb" strokeWidth={2} dot={{ r: 2.5 }} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[260px] flex items-center justify-center text-[12px] text-gray-400">
            {t('compliance.historyEmpty')}
          </div>
        )}
      </div>

      {/* Export range + find a scan */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-800 mb-1">{t('compliance.exportInterval')}</h3>
          <p className="text-[11px] text-gray-400 mb-3">{t('compliance.exportIntervalHint')}</p>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={expFmt} onChange={(e) => setExpFmt(e.target.value)}
              className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-brand/40"
            >
              <option value="csv">{t('compliance.exportCsv')}</option>
              <option value="json">{t('compliance.exportJson')}</option>
              <option value="pdf">{t('compliance.exportPdf')}</option>
            </select>
            <button
              onClick={exportInterval}
              disabled={!rows.length}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand text-white text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
            >
              <Download size={13} />{t('compliance.export')}
            </button>
            <span className="text-[11px] text-gray-400">{t('compliance.scansCount', { n: rows.length })}</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-800 mb-1">{t('compliance.findScan')}</h3>
          <p className="text-[11px] text-gray-400 mb-3">{t('compliance.findScanHint')}</p>
          <div className="flex items-center gap-2">
            <Search size={14} className="text-gray-400 flex-shrink-0" />
            <input
              type="datetime-local" value={searchAt} onChange={(e) => setSearchAt(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand/40"
            />
            {searchAt && (
              <button onClick={() => setSearchAt('')} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={14} /></button>
            )}
          </div>
          {searchAt && (
            <div className="mt-3 border-t border-gray-50 pt-2">
              {nearest.length ? (
                <div className="space-y-0.5">
                  <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">{t('compliance.nearestScans')}</div>
                  {nearest.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => openReport(r)}
                      disabled={loadingId === r.id}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 text-left"
                    >
                      <Clock size={12} className="text-gray-300 flex-shrink-0" />
                      <span className="text-[11px] text-gray-600 flex-1">{utcDate(r.collected_at)?.toLocaleString()}</span>
                      {!nodeId && <span className="text-[11px] text-gray-400">{r.hostname}</span>}
                      <span className={`text-[11px] font-semibold ${scoreColor(r.score)}`}>{r.score}%</span>
                      <ChevronRight size={12} className="text-gray-300" />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-gray-400">{t('compliance.noScansRange')}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Selected report */}
      {report && <ReportCard report={report} nodeId={nodeId} onClose={() => setReport(null)} t={t} />}

      {/* Scans table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-[13px] font-semibold text-gray-800">{t('compliance.allScans')}</h3>
          <span className="text-[11px] text-gray-400">{t('compliance.scansCount', { n: rows.length })}</span>
        </div>
        {loading ? (
          <div className="p-6 space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />)}</div>
        ) : !rows.length ? (
          <div className="p-8 text-center text-[12px] text-gray-400">{t('compliance.historyEmpty')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-2.5">{t('compliance.collectedAt')}</th>
                  {!nodeId && <th className="text-left px-5 py-2.5">{t('compliance.node')}</th>}
                  <th className="text-left px-5 py-2.5 w-40">{t('compliance.score')}</th>
                  <th className="text-left px-5 py-2.5">{t('compliance.controls')}</th>
                  <th className="text-left px-5 py-2.5">{t('compliance.source')}</th>
                  <th className="text-left px-5 py-2.5">{t('compliance.profile')}</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {shownRows.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-2.5 text-gray-500">{utcDate(r.collected_at)?.toLocaleString()}</td>
                    {!nodeId && <td className="px-5 py-2.5 text-gray-700 font-medium">{r.hostname || r.node_id}</td>}
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden max-w-[80px]">
                          <div className={`h-full rounded-full ${scoreBarColor(r.score)}`} style={{ width: `${r.score}%` }} />
                        </div>
                        <span className={`text-[12px] font-semibold ${scoreColor(r.score)}`}>{r.score}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-2.5 text-[11px] text-gray-500">
                      <b className="text-green-600">{r.passed_checks}</b> · <b className="text-red-600">{r.failed_checks}</b>
                      {r.skipped_checks ? <> · <b className="text-gray-400">{r.skipped_checks}</b></> : null}
                    </td>
                    <td className="px-5 py-2.5 text-gray-500">{r.source}</td>
                    <td className="px-5 py-2.5 text-gray-400">{r.profile || '—'}</td>
                    <td className="px-5 py-2.5 text-right">
                      <button
                        onClick={() => openReport(r)}
                        disabled={loadingId === r.id}
                        className="inline-flex items-center gap-1 text-[12px] text-brand hover:underline disabled:opacity-50"
                      >
                        {loadingId === r.id ? t('compliance.loadingReport') : t('compliance.viewExport')} <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > shownRows.length && (
              <div className="px-5 py-2.5 text-[11px] text-gray-400 border-t border-gray-50">
                {t('compliance.showingFirst', { shown: shownRows.length, total: rows.length })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
