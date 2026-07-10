import { Link, useNavigate } from 'react-router-dom'
import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, Tooltip,
} from 'recharts'
import { ShieldCheck, Server, Activity, AlertTriangle, ArrowRight } from 'lucide-react'
import { useT } from '../context/LangContext.jsx'
import { usePosture } from '../hooks/usePosture.js'
import { scoreColor, scoreBarColor } from '../lib/tw.js'
import { utcDate } from '../lib/time.js'
import Spinner from '../components/common/Spinner.jsx'

function fmtWhen(iso) {
  const d = utcDate(iso)
  return d ? d.toLocaleString() : '—'
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
        </>
      )}
    </div>
  )
}
