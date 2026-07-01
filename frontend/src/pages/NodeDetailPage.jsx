import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, CheckCircle, ChevronDown, ChevronRight,
  Network, RefreshCw, RotateCw, ShieldCheck, Wifi, Wrench, XCircle,
} from 'lucide-react'
import {
  getNode, pingNode, updateNode, changeNodeIdentity,
  getNodeCompliance, collectNodeCompliance, triggerRemediation, runClosedLoop,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge, btn, btnSm, btnDanger, scoreColor, scoreBarColor } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import StatusDot from '../components/common/StatusDot.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import DnsModal from '../components/nodes/DnsModal.jsx'

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function Field({ label, children, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-0.5">{label}</div>
      <div className={`text-[13px] text-gray-800 ${mono ? 'font-mono' : ''}`}>{children ?? '—'}</div>
    </div>
  )
}

// ── Change IP / DNS modal ─────────────────────────────────────────────────────
function ChangeIdentityModal({ node, onClose, onDone }) {
  const t = useT()
  const toast = useToast()
  const [ip, setIp] = useState(node.ip)
  const [hostname, setHostname] = useState(node.hostname)
  const [applySys, setApplySys] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const dirty = ip.trim() !== node.ip || hostname.trim() !== node.hostname || applySys
  const enrolled = node.puppet_enrolled || node.wazuh_enrolled

  async function apply() {
    setSaving(true)
    setError(null)
    try {
      const res = await changeNodeIdentity(node.id, {
        ip: ip.trim(),
        hostname: hostname.trim(),
        apply_system_hostname: applySys,
      })
      setResult(res)
      toast(t('nodeDetail.identity.applied'), 'success')
      onDone?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-[14px] font-semibold text-gray-900 flex items-center gap-2">
            <Network size={15} className="text-brand" />
            {t('nodeDetail.identity.modalTitle')}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {/* Danger banner */}
          <div className="flex items-start gap-2 px-3 py-2.5 bg-red-50 border border-red-100 rounded-lg">
            <AlertTriangle size={15} className="text-red-500 flex-shrink-0 mt-0.5" />
            <div className="text-[11px] text-red-700 leading-relaxed">
              <p className="font-semibold mb-0.5">{t('nodeDetail.identity.dangerTitle')}</p>
              <p>{t('nodeDetail.identity.dangerBody')}</p>
            </div>
          </div>

          {/* Preflight note */}
          <div className="flex items-start gap-2 px-3 py-2 bg-blue-50 rounded-lg">
            <ShieldCheck size={14} className="text-blue-500 flex-shrink-0 mt-0.5" />
            <p className="text-[11px] text-blue-700">{t('nodeDetail.identity.preflightNote')}</p>
          </div>

          {result ? (
            <ResultPanel result={result} t={t} />
          ) : (
            <>
              <div>
                <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.identity.newIp')}</label>
                <input
                  value={ip}
                  onChange={(e) => setIp(e.target.value)}
                  className="w-full mt-1 text-[13px] font-mono border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-brand"
                  placeholder="16.16.252.44"
                />
                <p className="text-[10px] text-gray-400 mt-0.5">{t('nodeDetail.identity.current')}: <span className="font-mono">{node.ip}</span></p>
              </div>

              <div>
                <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.identity.newHostname')}</label>
                <input
                  value={hostname}
                  onChange={(e) => setHostname(e.target.value)}
                  className="w-full mt-1 text-[13px] font-mono border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-brand"
                  placeholder="ec2-16-16-252-44.eu-north-1.compute.amazonaws.com"
                />
                <p className="text-[10px] text-gray-400 mt-0.5">{t('nodeDetail.identity.current')}: <span className="font-mono">{node.hostname}</span></p>
              </div>

              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" checked={applySys} onChange={(e) => setApplySys(e.target.checked)} className="mt-0.5" />
                <span className="text-[11px] text-gray-600">
                  <span className="font-medium">{t('nodeDetail.identity.applySys')}</span>
                  <span className="block text-gray-400">{t('nodeDetail.identity.applySysHint')}</span>
                </span>
              </label>

              {enrolled && (
                <div className="flex items-start gap-2 px-3 py-2 bg-amber-50 rounded-lg">
                  <AlertTriangle size={13} className="text-amber-500 flex-shrink-0 mt-0.5" />
                  <p className="text-[11px] text-amber-700">{t('nodeDetail.identity.enrolledWarn')}</p>
                </div>
              )}

              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-0.5" />
                <span className="text-[11px] text-gray-700 font-medium">{t('nodeDetail.identity.confirmLabel')}</span>
              </label>

              {error && <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-gray-100">
          {result ? (
            <button onClick={onClose} className={btn(true)}>{t('common.close')}</button>
          ) : (
            <>
              <button onClick={onClose} className={btn(false)}>{t('common.cancel')}</button>
              <button
                onClick={apply}
                disabled={!dirty || !confirmed || saving}
                className={`${btnDanger} disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {saving ? <Spinner size={12} /> : <Network size={13} />}
                {saving ? t('nodeDetail.identity.applying') : t('nodeDetail.identity.apply')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function ResultPanel({ result, t }) {
  const c = result.changed || {}
  const rows = [
    c.ip && { label: 'IP', from: c.ip.from, to: c.ip.to },
    c.hostname && { label: 'Hostname', from: c.hostname.from, to: c.hostname.to },
    c.fqdn && { label: 'FQDN', from: c.fqdn.from, to: c.fqdn.to },
  ].filter(Boolean)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-lg">
        <CheckCircle size={14} className="text-green-600" />
        <span className="text-[12px] text-green-700 font-medium">{t('nodeDetail.identity.applied')}</span>
      </div>
      {rows.length > 0 && (
        <div className="rounded-xl border border-gray-100 divide-y divide-gray-50">
          {rows.map((r) => (
            <div key={r.label} className="px-3 py-2 text-[12px]">
              <span className="font-medium text-gray-700">{r.label}</span>
              <div className="font-mono text-[11px] text-gray-500 mt-0.5">
                <span className="line-through opacity-60">{r.from}</span>
                <ChevronRight size={11} className="inline mx-1" />
                <span className="text-green-700">{r.to}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {result.wazuh_manager_reconfig?.is_wazuh_manager && (
        <WazuhRepointPanel reconfig={result.wazuh_manager_reconfig} />
      )}
      {result.warnings?.length > 0 && (
        <div className="px-3 py-2 bg-amber-50 rounded-lg space-y-1">
          {result.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-amber-700">
              <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Shown when the changed node is the Wazuh manager: confirms its agents were
// automatically re-pointed at the new address so they keep reporting.
function WazuhRepointPanel({ reconfig }) {
  const a = reconfig.agents || {}
  const total = a.agents_total ?? 0
  const ok = a.agents_repointed ?? 0
  const failed = a.agents_failed ?? 0
  const allGood = failed === 0
  return (
    <div className={`px-3 py-2 rounded-lg space-y-1.5 ${allGood ? 'bg-green-50' : 'bg-amber-50'}`}>
      <div className={`flex items-start gap-2 text-[11px] font-medium ${allGood ? 'text-green-700' : 'text-amber-700'}`}>
        {allGood ? <ShieldCheck size={12} className="flex-shrink-0 mt-0.5" /> : <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />}
        <span>
          This node is the Wazuh manager. New address{' '}
          <span className="font-mono">{reconfig.new_address}</span>
          {' '}propagated{total > 0 ? ` to ${ok}/${total} agent${total === 1 ? '' : 's'}` : ' (no enrolled agents)'}.
        </span>
      </div>
      {Array.isArray(a.results) && a.results.some((r) => !r.ok) && (
        <div className="pl-5 space-y-0.5">
          {a.results.filter((r) => !r.ok).map((r) => (
            <div key={r.node_id} className="text-[10px] font-mono text-amber-700">
              {r.hostname}: {r.error}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Compliance report card ────────────────────────────────────────────────────
function ReportCard({ report, t }) {
  const [open, setOpen] = useState(false)
  const score = report.score
  const details = report.details || []

  return (
    <div className="rounded-xl border border-gray-100 overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50/50 transition-colors text-left">
        {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
        <span className={badge(report.framework)}>{report.framework?.toUpperCase()}</span>
        <span className="text-[12px] text-gray-500">{report.source}</span>
        <div className="flex-1" />
        <span className="text-[11px] text-gray-400">{report.passed_checks}/{report.total_checks} {t('nodeDetail.compliance.passing')}</span>
        <span className={`text-[15px] font-semibold ${scoreColor(score)}`}>{score}%</span>
      </button>

      <div className="px-4 pb-2">
        <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
          <div className={`h-full ${scoreBarColor(score)} transition-all`} style={{ width: `${score}%` }} />
        </div>
        <div className="text-[10px] text-gray-400 mt-1.5 pb-1">{t('nodeDetail.compliance.collectedAt')} {fmtDate(report.collected_at)}</div>
      </div>

      {open && details.length > 0 && (
        <div className="border-t border-gray-100 divide-y divide-gray-50">
          {details.map((d, i) => (
            <div key={i} className="flex items-center gap-2.5 px-4 py-2">
              {d.status === 'pass' ? <CheckCircle size={13} className="text-green-600 flex-shrink-0" />
                : d.status === 'fail' ? <XCircle size={13} className="text-red-500 flex-shrink-0" />
                : <div className="w-[13px] h-[13px] rounded-full bg-gray-200 flex-shrink-0" />}
              <span className="text-[11px] font-mono text-gray-400 w-16 flex-shrink-0">{d.control_id}</span>
              <span className="text-[12px] text-gray-700 flex-1">{d.title}</span>
              {d.value !== undefined && <span className="text-[12px] font-mono text-gray-500">{d.value}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function NodeDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const t = useT()
  const toast = useToast()

  const { data: node, loading, error, refetch } = useApi(() => getNode(id), { deps: [id] })
  const { data: compliance, refetch: refetchCompliance } = useApi(() => getNodeCompliance(id), { deps: [id] })

  const [pinging, setPinging] = useState(false)
  const [dnsOpen, setDnsOpen] = useState(false)
  const [identityOpen, setIdentityOpen] = useState(false)
  const [collecting, setCollecting] = useState(false)
  const [remediating, setRemediating] = useState(false)
  const [closedLooping, setClosedLooping] = useState(false)

  // editable settings
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [savingSettings, setSavingSettings] = useState(false)

  function startEdit() {
    setForm({
      description: node.description || '',
      tags: (node.tags || []).join(', '),
      ssh_port: node.ssh_port,
      ssh_user: node.ssh_user,
      ssh_key_path: node.ssh_key_path || '',
    })
    setEditing(true)
  }

  async function saveSettings() {
    setSavingSettings(true)
    try {
      await updateNode(id, {
        description: form.description,
        tags: form.tags.split(',').map((s) => s.trim()).filter(Boolean),
        ssh_port: Number(form.ssh_port),
        ssh_user: form.ssh_user,
        ssh_key_path: form.ssh_key_path || null,
      })
      toast(t('nodeDetail.settings.saved'), 'success')
      setEditing(false)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSavingSettings(false)
    }
  }

  async function handlePing() {
    setPinging(true)
    try {
      const r = await pingNode(id)
      toast(r.reachable ? t('nodes.pingResult', { hostname: node.hostname, ms: r.latency_ms })
                        : t('nodes.pingFailed', { hostname: node.hostname }),
            r.reachable ? 'success' : 'warning')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setPinging(false)
    }
  }

  async function handleCollect() {
    setCollecting(true)
    try {
      const r = await collectNodeCompliance(id)
      toast(t('nodeDetail.compliance.collected', { n: r.collected?.length ?? 0 }), 'success')
      refetchCompliance()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setCollecting(false)
    }
  }

  async function handleRemediate() {
    setRemediating(true)
    try {
      const r = await triggerRemediation(id, 'Manual remediation from node detail')
      toast(r.message || t('nodeDetail.compliance.remediated'), r.outcome === 'failed' ? 'error' : 'success')
      refetchCompliance()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRemediating(false)
    }
  }

  async function handleClosedLoop() {
    setClosedLooping(true)
    try {
      const r = await runClosedLoop({ nodeId: id, description: 'Closed loop from node detail' })
      const n = (r.nodes && r.nodes[0]) || {}
      const status = n.status || (r.succeeded ? 'success' : 'failed')
      toast(`Closed loop ${status}: enforced${r.rescan ? ' + re-scanned' : ''}.`,
        status === 'failed' ? 'error' : 'success')
      refetchCompliance()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setClosedLooping(false)
    }
  }

  if (loading) {
    return <div className="p-6"><Spinner size={20} /></div>
  }
  if (error || !node) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/nodes')} className={btn(false)}><ArrowLeft size={14} />{t('nodeDetail.back')}</button>
        <p className="mt-4 text-[13px] text-red-600">{error || t('nodeDetail.notFound')}</p>
      </div>
    )
  }

  const enrolled = node.puppet_enrolled || node.wazuh_enrolled
  const reports = compliance?.reports || []
  const remediations = compliance?.remediations || []

  return (
    <div className="p-6 max-w-5xl">
      {/* Back + header */}
      <button onClick={() => navigate('/nodes')} className="flex items-center gap-1.5 text-[12px] text-gray-500 hover:text-gray-800 transition-colors mb-4">
        <ArrowLeft size={14} />{t('nodeDetail.back')}
      </button>

      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <StatusDot status={node.status} />
          <div>
            <h2 className="text-[18px] font-semibold text-gray-900">{node.hostname}</h2>
            {node.fqdn && node.fqdn !== node.hostname && (
              <p className="text-[12px] font-mono text-gray-400">{node.fqdn}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handlePing} disabled={pinging} className={btnSm(false)}>
            {pinging ? <Spinner size={12} /> : <Wifi size={12} />}{t('nodeDetail.ping')}
          </button>
          <button onClick={() => setDnsOpen(true)} className={btnSm(false)}>
            <Network size={12} />{t('nodeDetail.checkDns')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Overview */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-900 mb-4">{t('nodeDetail.overview')}</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label={t('nodeDetail.ip')} mono>{node.ip}</Field>
            <Field label={t('nodeDetail.status')}><span className="capitalize">{node.status}</span></Field>
            <Field label={t('nodeDetail.os')}>
              {node.os_family ? <span className={badge(node.os_family)}>{node.os_family}</span> : '—'}
              {node.os_name && <div className="text-[11px] text-gray-400 mt-0.5">{node.os_name}</div>}
            </Field>
            <Field label={t('nodeDetail.dns')}>
              {node.dns_resolves === true ? <span className={badge('success')}>OK</span>
                : node.dns_resolves === false ? <span className={badge('danger')}>{t('nodeDetail.dnsFail')}</span>
                : <span className={badge('gray')}>—</span>}
            </Field>
            <Field label={t('nodeDetail.lastSeen')}>{fmtDate(node.last_seen)}</Field>
            <Field label={t('nodeDetail.created')}>{fmtDate(node.created_at)}</Field>
          </div>
        </div>

        {/* Enrollment */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-900 mb-4">{t('nodeDetail.enrollment')}</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-gray-600">Puppet</span>
              <span className={badge(node.puppet_enrolled ? 'success' : 'gray')}>
                {node.puppet_enrolled ? t('common.enrolled') : t('common.notEnrolled')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-gray-600">Wazuh</span>
              <span className={badge(node.wazuh_enrolled ? 'success' : 'gray')}>
                {node.wazuh_enrolled ? t('common.enrolled') : t('common.notEnrolled')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-gray-600">{t('infra.scanEngine')}</span>
              <span className={badge(node.scan_ready ? 'success' : 'gray')}>
                {node.scan_ready ? t('common.enrolled') : t('common.notEnrolled')}
              </span>
            </div>
          </div>
        </div>

        {/* Identity (danger) */}
        <div className="bg-white rounded-2xl border border-red-100 p-5">
          <h3 className="text-[13px] font-semibold text-gray-900 mb-1 flex items-center gap-2">
            <Network size={14} className="text-red-500" />{t('nodeDetail.identity.title')}
          </h3>
          <p className="text-[11px] text-gray-400 mb-4">{t('nodeDetail.identity.subtitle')}</p>
          <div className="grid grid-cols-1 gap-3 mb-4">
            <Field label={t('nodeDetail.ip')} mono>{node.ip}</Field>
            <Field label={t('nodeDetail.hostname')} mono>{node.hostname}</Field>
          </div>
          <button onClick={() => setIdentityOpen(true)} className={btnDanger}>
            <Network size={13} />{t('nodeDetail.identity.changeBtn')}
          </button>
        </div>

        {/* Settings */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[13px] font-semibold text-gray-900">{t('nodeDetail.settings.title')}</h3>
            {!editing && <button onClick={startEdit} className={btnSm(false)}>{t('common.edit')}</button>}
          </div>
          {editing ? (
            <div className="space-y-3">
              <div>
                <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.settings.description')}</label>
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full mt-1 text-[13px] border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-brand" />
              </div>
              <div>
                <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.settings.tags')}</label>
                <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  className="w-full mt-1 text-[13px] border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-brand" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.settings.sshPort')}</label>
                  <input value={form.ssh_port} onChange={(e) => setForm({ ...form, ssh_port: e.target.value })}
                    className="w-full mt-1 text-[13px] font-mono border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-brand" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.settings.sshUser')}</label>
                  <input value={form.ssh_user} onChange={(e) => setForm({ ...form, ssh_user: e.target.value })}
                    className="w-full mt-1 text-[13px] font-mono border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-brand" />
                </div>
              </div>
              <div>
                <label className="text-[11px] font-medium text-gray-600">{t('nodeDetail.settings.sshKeyPath')}</label>
                <input value={form.ssh_key_path} onChange={(e) => setForm({ ...form, ssh_key_path: e.target.value })}
                  className="w-full mt-1 text-[13px] font-mono border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-brand" />
              </div>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button onClick={() => setEditing(false)} className={btnSm(false)}>{t('common.cancel')}</button>
                <button onClick={saveSettings} disabled={savingSettings} className={btnSm(true)}>
                  {savingSettings ? <Spinner size={12} /> : null}{t('common.save')}
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <Field label={t('nodeDetail.settings.sshUser')} mono>{node.ssh_user}</Field>
              <Field label={t('nodeDetail.settings.sshPort')} mono>{node.ssh_port}</Field>
              <Field label={t('nodeDetail.settings.description')}>{node.description}</Field>
              <Field label={t('nodeDetail.settings.tags')}>
                {node.tags?.length ? node.tags.map((tg) => <span key={tg} className={`${badge('gray')} mr-1`}>{tg}</span>) : '—'}
              </Field>
              <Field label={t('nodeDetail.settings.sshKeyPath')} mono>{node.ssh_key_path || t('nodeDetail.settings.default')}</Field>
            </div>
          )}
        </div>
      </div>

      {/* Compliance */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 mt-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[13px] font-semibold text-gray-900 flex items-center gap-2">
            <ShieldCheck size={15} className="text-brand" />{t('nodeDetail.compliance.title')}
          </h3>
          <div className="flex items-center gap-2">
            <button onClick={handleCollect} disabled={collecting}
              className={`${btnSm(true)} disabled:opacity-40 disabled:cursor-not-allowed`}>
              {collecting ? <Spinner size={12} /> : <RefreshCw size={12} />}{t('nodeDetail.compliance.collect')}
            </button>
            <button onClick={handleRemediate} disabled={remediating || !node.puppet_enrolled} title={!node.puppet_enrolled ? t('nodeDetail.compliance.puppetFirst') : ''}
              className={`${btnSm(false)} disabled:opacity-40 disabled:cursor-not-allowed`}>
              {remediating ? <Spinner size={12} /> : <Wrench size={12} />}{t('nodeDetail.compliance.remediate')}
            </button>
            <button onClick={handleClosedLoop} disabled={closedLooping || !node.puppet_enrolled}
              title={!node.puppet_enrolled ? t('nodeDetail.compliance.puppetFirst') : 'Enforce with Puppet, then re-scan'}
              className={`${btnSm(true)} disabled:opacity-40 disabled:cursor-not-allowed`}>
              {closedLooping ? <Spinner size={12} /> : <RotateCw size={12} />}Closed loop
            </button>
          </div>
        </div>



        {reports.length === 0 ? (
          <EmptyState icon={ShieldCheck} title={t('nodeDetail.compliance.noReports')} description={t('nodeDetail.compliance.noReportsDesc')} />
        ) : (
          <div className="space-y-2">
            {reports.map((r) => <ReportCard key={r.id} report={r} t={t} />)}
          </div>
        )}

        {/* Remediation history */}
        {remediations.length > 0 && (
          <div className="mt-5">
            <h4 className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold mb-2">{t('nodeDetail.compliance.remediationHistory')}</h4>
            <div className="rounded-xl border border-gray-100 divide-y divide-gray-50">
              {remediations.map((rem) => (
                <div key={rem.id} className="flex items-center gap-3 px-4 py-2.5">
                  <span className={badge(rem.outcome === 'success' ? 'success' : rem.outcome === 'failed' ? 'danger' : 'gray')}>
                    {rem.outcome}
                  </span>
                  <span className="text-[12px] text-gray-600">{t('nodeDetail.compliance.resourcesFixed', { n: rem.resources_fixed })}</span>
                  <div className="flex-1" />
                  <span className="text-[11px] text-gray-400">{fmtDate(rem.triggered_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {dnsOpen && <DnsModal node={node} onClose={() => setDnsOpen(false)} onRefetch={refetch} />}
      {identityOpen && (
        <ChangeIdentityModal
          node={node}
          onClose={() => setIdentityOpen(false)}
          onDone={() => { refetch(); refetchCompliance() }}
        />
      )}
    </div>
  )
}
