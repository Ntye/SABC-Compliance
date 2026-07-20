import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, Tooltip,
} from 'recharts'
import { ShieldCheck, Server, Activity, AlertTriangle, ArrowRight, Timer } from 'lucide-react'
import { useT } from '../context/LangContext.jsx'
import { usePosture } from '../hooks/usePosture.js'
import { getDetectionTimingStats } from '../lib/api.js'
import { scoreColor, scoreBarColor } from '../lib/tw.js'
import { utcDate } from '../lib/time.js'
import Spinner from '../components/common/Spinner.jsx'

function fmtWhen(iso) {
  const d = utcDate(iso)
  return d ? d.toLocaleString() : '—'
}

// Human duration from seconds: 840ms · 2.4s · 3m 12s · 1h 04m.
function fmtDur(s) {
  if (s == null) return '—'
  if (s < 1) return `${Math.round(s * 1000)}ms`
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`
}

// min / avg / max triple for one metric of one OS family.
function TimingCells({ stats }) {
  if (!stats || stats.count === 0) {
    return <td colSpan={3} className="px-4 py-2.5 text-center text-gray-300">—</td>
  }
  return (
    <>
      <td className="px-4 py-2.5 text-right font-mono text-[11px] text-gray-500">{fmtDur(stats.min_s)}</td>
      <td className="px-4 py-2.5 text-right font-mono text-[11px] font-semibold text-gray-800">{fmtDur(stats.avg_s)}</td>
      <td className="px-4 py-2.5 text-right font-mono text-[11px] text-gray-500">{fmtDur(stats.max_s)}</td>
    </>
  )
}

// Detection latency (agent event → platform ingest) and enforcement duration
// (remediation triggered → completed) — min/avg/max per OS family.
function ResponseTimesCard({ t }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => getDetectionTimingStats()
      .then((s) => { if (alive) setStats(s) })
      .catch(() => {})
    load()
    const id = setInterval(load, 60000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const rows = stats?.families || []
  const overall = stats?.overall
  const hasAny = rows.some((r) => r.detection.count > 0 || r.enforcement.count > 0 || r.closed_loop?.count > 0)

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">
        <Timer size={12} />
        {t('dash.responseTimes')}
      </div>
      {!hasAny ? (
        <div className="text-[12px] text-gray-300">{t('dash.responseTimesEmpty')}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100">
                <th rowSpan={2} title={t('dash.rtFamilyHint')}
                    className="text-left px-4 py-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider align-bottom cursor-help">{t('dash.rtFamily')}</th>
                <th colSpan={3} title={t('dash.rtDetectionHint')}
                    className="text-center px-4 py-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-l border-gray-50 cursor-help">{t('dash.rtDetection')}</th>
                <th rowSpan={2} title={t('dash.rtSamplesDetectionHint')}
                    className="text-right px-4 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider align-bottom cursor-help">{t('dash.rtSamples')}</th>
                <th colSpan={3} title={t('dash.rtEnforcementHint')}
                    className="text-center px-4 py-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-l border-gray-50 cursor-help">{t('dash.rtEnforcement')}</th>
                <th rowSpan={2} title={t('dash.rtSamplesEnforcementHint')}
                    className="text-right px-4 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider align-bottom cursor-help">{t('dash.rtSamples')}</th>
                <th colSpan={3} title={t('dash.rtClosedLoopHint')}
                    className="text-center px-4 py-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-l border-gray-50 cursor-help">{t('dash.rtClosedLoop')}</th>
                <th rowSpan={2} title={t('dash.rtSamplesClosedLoopHint')}
                    className="text-right px-4 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider align-bottom cursor-help">{t('dash.rtSamples')}</th>
              </tr>
              <tr className="border-b border-gray-100">
                {['rtMin', 'rtAvg', 'rtMax', 'rtMin', 'rtAvg', 'rtMax', 'rtMin', 'rtAvg', 'rtMax'].map((k, i) => (
                  <th key={i} title={t(`dash.${k}Hint`)}
                      className={`text-right px-4 py-1.5 text-[10px] font-medium text-gray-400 uppercase tracking-wider cursor-help ${i % 3 === 0 ? 'border-l border-gray-50' : ''}`}>
                    {t(`dash.${k}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map((r) => (
                <tr key={r.os_family}>
                  <td className={`px-4 py-2.5 font-medium text-gray-800 ${r.os_family === 'Unknown' ? 'cursor-help' : ''}`}
                      title={r.os_family === 'Unknown' ? t('dash.rtUnknownHint') : undefined}>
                    {r.os_family}
                  </td>
                  <TimingCells stats={r.detection} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{r.detection.count || '—'}</td>
                  <TimingCells stats={r.enforcement} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{r.enforcement.count || '—'}</td>
                  <TimingCells stats={r.closed_loop} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{r.closed_loop?.count || '—'}</td>
                </tr>
              ))}
              {overall && rows.length > 1 && (
                <tr className="bg-gray-50/60">
                  <td className="px-4 py-2.5 font-semibold text-gray-500 cursor-help" title={t('dash.rtOverallHint')}>{t('dash.rtOverall')}</td>
                  <TimingCells stats={overall.detection} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{overall.detection.count || '—'}</td>
                  <TimingCells stats={overall.enforcement} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{overall.enforcement.count || '—'}</td>
                  <TimingCells stats={overall.closed_loop} />
                  <td className="px-4 py-2.5 text-right text-[11px] text-gray-400">{overall.closed_loop?.count || '—'}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// A titled panel showing per-bucket average scores as labelled meters.
function BreakdownCard({ title, rows }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4">
      <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</div>
      {rows.length === 0 ? (
        <div className="text-[12px] text-gray-300">—</div>
      ) : (
        <div className="space-y-2.5">
          {rows.map((r) => (
            <div key={r.key} className="flex items-center gap-3">
              <span className="text-[12px] text-gray-600 w-24 truncate" title={r.key}>{r.key}</span>
              <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${r.score}%`, background: scoreBarColor(r.score) }} />
              </div>
              <span className={`text-[12px] font-semibold w-9 text-right ${scoreColor(r.score)}`}>{r.score}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// A large stat tile with an icon, value and label — the CRICLO right-column KPIs.
function StatTile({ icon: Icon, value, label, sub, accent, to }) {
  const body = (
    <div className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4 h-full hover:border-gray-200 transition-colors">
      <div className="w-9 h-9 rounded-lg bg-gray-50 flex items-center justify-center flex-shrink-0">
        <Icon size={18} className="text-gray-400" />
      </div>
      <div className="min-w-0">
        <div className={`text-[22px] font-bold leading-none ${accent || 'text-gray-900'}`}>{value}</div>
        <div className="text-[11px] text-gray-400 mt-1 truncate">{label}</div>
        {sub && <div className="text-[10px] text-gray-300 truncate">{sub}</div>}
      </div>
    </div>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

export default function OverviewPage() {
  const t = useT()
  const navigate = useNavigate()
  const { data, loading, error } = usePosture()

  if (loading && !data) {
    return <div className="p-10 flex justify-center"><Spinner /></div>
  }
  if (error) {
    return <div className="p-6 text-[13px] text-red-600">{error}</div>
  }

  const hasData = data && data.scanned > 0

  return (
    <div className="p-6 space-y-5">
      {/* Title row */}
      <div className="flex items-end justify-between">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('dash.title')}</h2>
        {data?.lastSweep && (
          <div className="text-[11px] text-gray-400">
            {t('dash.lastSweep')}: <span className="text-gray-500">{fmtWhen(data.lastSweep)}</span>
          </div>
        )}
      </div>

      {!hasData ? (
        <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
          <ShieldCheck size={28} className="text-gray-200 mx-auto mb-3" />
          <div className="text-[14px] font-medium text-gray-700">{t('dash.noData')}</div>
          <div className="text-[12px] text-gray-400 mt-1">{t('dash.noDataSub')}</div>
          <button
            onClick={() => navigate('/nodes')}
            className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 text-[12px] font-medium bg-brand text-white rounded-lg hover:bg-brand/90"
          >
            {t('dash.goToNodes')} <ArrowRight size={13} />
          </button>
        </div>
      ) : (
        <>
          {/* Row 1: global score + trend, and two breakdowns */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('dash.trend')}</div>
              <div className={`text-[40px] font-extrabold leading-tight ${scoreColor(data.globalScore)}`}>
                {data.globalScore}
                <span className="text-[16px] font-semibold text-gray-300 ml-1">/100</span>
              </div>
              <div className="text-[11px] text-gray-400 -mt-1 mb-2">
                {data.passed}/{data.passed + data.failed} {t('dash.passing')}
              </div>
              <div className="h-16">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.scoreByNode.slice(0, 24)} barCategoryGap={2}>
                    <XAxis dataKey="name" hide />
                    <Tooltip
                      cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #eee' }}
                      formatter={(v) => [`${v}%`, 'Score']}
                    />
                    <Bar dataKey="score" radius={[2, 2, 0, 0]}>
                      {data.scoreByNode.slice(0, 24).map((d, i) => (
                        <Cell key={i} fill={scoreBarColor(d.score)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <BreakdownCard title={t('dash.byTier')} rows={data.byTier} />
            <BreakdownCard title={t('dash.byOs')} rows={data.byOs} />
          </div>

          {/* Row 2: framework breakdown + KPI tiles */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <BreakdownCard title={t('dash.byFramework')} rows={data.byFramework} />

            <div className="xl:col-span-2 grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatTile
                icon={AlertTriangle}
                value={data.outOfCompliance}
                label={t('dash.outOfCompliance')}
                sub={t('dash.outOfComplianceSub')}
                accent={data.outOfCompliance > 0 ? 'text-red-600' : 'text-green-600'}
                to="/compliance"
              />
              <StatTile
                icon={Activity}
                value={data.activeAlerts}
                label={t('dash.openDetections')}
                sub={t('dash.openDetectionsSub')}
                accent={data.activeAlerts > 0 ? 'text-amber-600' : 'text-gray-900'}
                to="/detection"
              />
              <StatTile
                icon={Server}
                value={data.scanned}
                label={t('dash.nodesScanned')}
                to="/nodes"
              />
              <StatTile
                icon={ShieldCheck}
                value={data.critical}
                label={t('dash.criticalFindings')}
                accent={data.critical > 0 ? 'text-red-600' : 'text-gray-900'}
                to="/compliance"
              />
            </div>
          </div>

          {/* Row 3: detection & enforcement response times per OS family */}
          <ResponseTimesCard t={t} />
        </>
      )}
    </div>
  )
}
