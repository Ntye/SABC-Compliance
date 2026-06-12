import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { ShieldCheck, RefreshCw, ChevronRight, AlertTriangle } from 'lucide-react'
import { getComplianceSummary } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { badge, scoreColor, scoreBarColor } from '../lib/tw.js'

const C = { pass: '#16a34a', fail: '#dc2626', skip: '#9ca3af', high: '#dc2626' }

// Pick the report that best represents a node's security posture.
// InSpec is the structured scan; fall back to the CIS shell check, then anything.
function primaryReport(node) {
  const reports = node.reports || []
  return (
    reports.find((r) => r.source === 'inspec') ||
    reports.find((r) => r.source === 'cis-ssh') ||
    reports.find((r) => r.source !== 'puppet') ||
    null
  )
}

function sourceLabel(t, source) {
  if (source === 'inspec') return t('compliance.sourceInspec')
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

export default function CompliancePage() {
  const t = useT()
  const { data, loading, refetch } = useApi(getComplianceSummary)

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
        <button
          onClick={refetch}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-[12px] text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          {t('common.refresh') || 'Refresh'}
        </button>
      </div>

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
                      {r ? <span className={badge(r.source === 'inspec' ? 'info' : 'gray')}>{sourceLabel(t, r.source)}</span> : '—'}
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
