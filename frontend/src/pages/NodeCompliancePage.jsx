import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts'
import {
  ArrowLeft, Play, Wrench, CheckCircle2, XCircle, MinusCircle, ChevronDown,
} from 'lucide-react'
import { getNodeCompliance, collectNodeCompliance, triggerRemediation } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { badge, scoreColor } from '../lib/tw.js'

const C = { pass: '#16a34a', fail: '#dc2626', skip: '#9ca3af' }
const SEV = { high: '#dc2626', medium: '#f59e0b', low: '#3b82f6', info: '#9ca3af' }

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
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-3 px-5 py-3 hover:bg-gray-50/50 text-left">
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
          <span
            className="inline-flex items-center px-2 py-[3px] rounded-full text-[10px] font-medium"
            style={{ background: `${SEV[sev]}22`, color: SEV[sev] }}
          >
            {t(`compliance.${sev}`)}
          </span>
          <ChevronDown size={14} className={`text-gray-300 transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {open && (
        <div className="px-5 pb-3 pl-[42px] space-y-1.5">
          {ctrl.desc && <p className="text-[12px] text-gray-500">{ctrl.desc}</p>}
          {ctrl.message && (
            <pre className="text-[11px] text-gray-600 bg-gray-50 border border-gray-100 rounded-md p-2 whitespace-pre-wrap font-mono">{ctrl.message}</pre>
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

export default function NodeCompliancePage() {
  const { id } = useParams()
  const t = useT()
  const toast = useToast()
  const { data, loading, refetch } = useApi(() => getNodeCompliance(id), { deps: [id] })
  const [scanning, setScanning] = useState(false)
  const [remediating, setRemediating] = useState(false)
  const [filter, setFilter] = useState('all')

  const report = useMemo(() => (data ? primaryReport(data.reports || []) : null), [data])

  const history = useMemo(() => {
    if (!data) return []
    return (data.reports || [])
      .filter((r) => r.source === 'inspec' || r.source === 'cis-ssh')
      .map((r) => ({ ts: new Date(r.collected_at).getTime(), date: new Date(r.collected_at).toLocaleDateString(), score: r.score }))
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

  const controls = useMemo(() => {
    const details = report?.details || []
    if (filter === 'failed') return details.filter((d) => d.status === 'fail')
    if (filter === 'passed') return details.filter((d) => d.status === 'pass')
    // sort: failed first, then by severity weight
    const w = { high: 0, medium: 1, low: 2, info: 3 }
    return [...details].sort((a, b) => {
      const sa = a.status === 'fail' ? 0 : a.status === 'skip' ? 2 : 1
      const sb = b.status === 'fail' ? 0 : b.status === 'skip' ? 2 : 1
      if (sa !== sb) return sa - sb
      return (w[a.severity] ?? 9) - (w[b.severity] ?? 9)
    })
  }, [report, filter])

  const enrolled = data && (data.puppet_enrolled || data.wazuh_enrolled)

  async function runScan() {
    setScanning(true)
    try {
      const res = await collectNodeCompliance(id)
      toast(t('compliance.scanned', { n: res.collected?.length || 0 }), 'success')
      await refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setScanning(false)
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
          <button
            onClick={runScan}
            disabled={scanning || !enrolled}
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

      {!enrolled && !loading && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-[12px] text-amber-800">
          {t('compliance.enrollFirst')}
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

          {/* Controls list */}
          <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-gray-800">{t('compliance.controlsTitle')}</h3>
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
            {controls.length ? controls.map((ctrl) => (
              <ControlRow key={ctrl.control_id} ctrl={ctrl} t={t} />
            )) : (
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
