import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, CheckCircle, ChevronDown, Cpu, Link, RefreshCw,
  Search, Server, ShieldCheck, XCircle,
} from 'lucide-react'
import {
  getInfrastructureStatus, installService, listNodes,
  setPuppetMasterHost, setWazuhManagerHost, jobWsUrl,
  checkPuppetAgentPlatform, exportPuppetCa,
  getInspecStatus, installInspecOnController, verifyInspecAllNodes, verifyInspecNode,
} from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, btnSm, logLineClass } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

// ── Helpers ───────────────────────────────────────────────────────────────────

function utcDate(iso) {
  if (!iso) return null
  return new Date(/[Zz]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z')
}

function timeAgo(iso) {
  if (!iso) return 'never'
  const s = Math.floor((Date.now() - utcDate(iso)) / 1000)
  if (s < 60)  return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60)  return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24)  return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7)   return `${d}d ago`
  return `${Math.floor(d / 7)}w ago`
}

function Pip({ ok, label, tooltip }) {
  const dot = ok === true
    ? <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
    : ok === 'warn'
      ? <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
      : <span className="w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0" />
  const textCls = ok === true
    ? 'text-green-700'
    : ok === 'warn'
      ? 'text-amber-600'
      : 'text-gray-400'
  const defaultLabel = ok === true ? 'Installed' : ok === 'warn' ? 'Unreachable' : 'Not installed'
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-medium ${textCls}`}
      title={tooltip || undefined}
    >
      {dot}
      {label || defaultLabel}
    </span>
  )
}

// ── Edition badge ─────────────────────────────────────────────────────────────

function EditionBadge({ edition, t }) {
  if (!edition) return null
  if (edition === 'enterprise') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        {t('infra.editionEnterprise')}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-50 text-green-700 border border-green-200">
      {t('infra.editionCommunity')}
    </span>
  )
}

// ── Migrate CA modal ──────────────────────────────────────────────────────────

function MigrateCAModal({ onClose, onJobStarted, t }) {
  const [confirmed, setConfirmed] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [done, setDone] = useState(false)
  const toast = useToast()

  async function handleExport() {
    setExporting(true)
    try {
      const job = await exportPuppetCa()
      setDone(true)
      onJobStarted(job)
    } catch (err) {
      toast(`${t('infra.migrateCaError')}: ${err.message}`, 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-[14px] font-semibold text-gray-900">{t('infra.migrateCaTitle')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <p className="text-[12px] text-gray-600 leading-relaxed">{t('infra.migrateCaDesc')}</p>

          <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl">
            <AlertTriangle size={14} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-[11px] text-amber-800 leading-relaxed">{t('infra.migrateCaWarning')}</p>
          </div>

          <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
            <p className="text-[11px] font-semibold text-gray-700 mb-1">{t('infra.migrateCaStep1')}</p>
            <p className="text-[11px] text-gray-500">{t('infra.migrateCaStep1Desc')}</p>
          </div>

          {done && (
            <div className="flex items-start gap-2 p-3 bg-green-50 border border-green-200 rounded-xl">
              <CheckCircle size={14} className="text-green-600 mt-0.5 flex-shrink-0" />
              <p className="text-[12px] text-green-800 leading-relaxed">{t('infra.migrateCaSuccess')}</p>
            </div>
          )}

          {!done && (
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-0.5 accent-brand flex-shrink-0"
              />
              <span className="text-[11px] text-gray-600">{t('infra.migrateCaConfirmLabel')}</span>
            </label>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className={btn(false)}>{t('common.close')}</button>
          {!done && (
            <button
              onClick={handleExport}
              disabled={!confirmed || exporting}
              className={btn(confirmed && !exporting)}
            >
              {exporting && <Spinner size={13} />}
              {exporting ? t('infra.migrateCaExporting') : t('infra.migrateCaStart')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ configured, reachable, t }) {
  if (!configured) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-500">
      {t('infra.notConfigured')}
    </span>
  )
  if (reachable === null || reachable === undefined) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-600">
      {t('infra.configured')}
    </span>
  )
  if (reachable) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-50 text-green-700">
      <CheckCircle size={9} /> {t('infra.reachable')}
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-600">
      <XCircle size={9} /> {t('infra.unreachable')}
    </span>
  )
}

// ── Log drawer (used for install jobs) ───────────────────────────────────────

function LogDrawer({ job, onClose, t }) {
  const [lines, setLines] = useState([])
  const [done, setDone] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!job) return
    const ws = new WebSocket(jobWsUrl(job.id))
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      setLines((prev) => [...prev, msg])
      if (msg.level === 'system') setDone(true)
    }
    ws.onerror = () => setDone(true)
    ws.onclose  = () => setDone(true)
    return () => ws.close()
  }, [job?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  if (!job) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-3xl bg-console-bg rounded-2xl overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            {!done && <Spinner size={12} className="text-console-accent" />}
            {done && <CheckCircle size={13} className="text-green-400" />}
            <span className="text-[12px] font-medium text-console-text">
              Job {job.id.slice(0, 8)} — {done ? t('infra.jobCompleted') : t('infra.jobRunningState')}
            </span>
          </div>
          <button onClick={onClose} className="text-console-muted hover:text-console-text text-[18px] leading-none">&times;</button>
        </div>
        <div className="h-80 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed">
          {lines.map((l, i) => (
            <div key={i} className={logLineClass(l)}>{l.line || ' '}</div>
          ))}
          <div ref={bottomRef} />
        </div>
        {done && (
          <div className="px-5 py-3 border-t border-white/10 flex justify-end">
            <button onClick={onClose} className={btnSm(true)}>{t('common.close')}</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Connect host form ─────────────────────────────────────────────────────────

function ConnectForm({ service, onSave, onCancel, t }) {
  const [host, setHost] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSave() {
    if (!host.trim()) return
    setSaving(true)
    try {
      const fn = service === 'puppet' ? setPuppetMasterHost : setWazuhManagerHost
      const result = await fn(host.trim())
      toast(
        result.reachable
          ? t('infra.saveDone', { host: result.host, port: result.port })
          : t('infra.saveWarning', { port: result.port }),
        result.reachable ? 'success' : 'warning',
      )
      onSave()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const label       = service === 'puppet' ? t('infra.connectToPuppet')  : t('infra.connectToWazuh')
  const placeholder = service === 'puppet' ? 'puppet.example.com' : 'wazuh.example.com'

  return (
    <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-200 space-y-3">
      <p className="text-[11px] font-semibold text-gray-600 uppercase tracking-wider">{label}</p>
      <div className="flex gap-2">
        <input
          autoFocus
          value={host}
          onChange={(e) => setHost(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          placeholder={placeholder}
          className="flex-1 px-3 py-2 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
        <button onClick={handleSave} disabled={saving || !host.trim()} className={btn(true)}>
          {saving && <Spinner size={13} />}
          {saving ? t('infra.saving') : t('common.save')}
        </button>
        <button onClick={onCancel} className={btn(false)}>{t('common.cancel')}</button>
      </div>
    </div>
  )
}

// ── Install modal (master services) ──────────────────────────────────────────

function InstallModal({ service, nodes, onClose, onJobStarted, t }) {
  const [selectedNode, setSelectedNode] = useState('')
  const [starting, setStarting]         = useState(false)
  const [platformCheck, setPlatformCheck]     = useState(null)
  const [checkingPlatform, setCheckingPlatform] = useState(false)
  const toast = useToast()

  const serviceLabels = {
    'puppet-master': t('infra.installPuppetMaster'),
    'wazuh-manager': t('infra.installWazuhManager'),
  }
  const label = serviceLabels[service] || service

  async function handleNodeChange(nodeId) {
    setSelectedNode(nodeId)
    setPlatformCheck(null)
    if (!nodeId) return
    setCheckingPlatform(true)
    try {
      const result = await checkPuppetAgentPlatform(nodeId)
      setPlatformCheck(result)
    } catch (_) {}
    finally { setCheckingPlatform(false) }
  }

  async function handleStart() {
    if (!selectedNode) return
    setStarting(true)
    try {
      const job = await installService(service, selectedNode)
      onJobStarted(job)
      onClose()
    } catch (err) {
      toast(err.message, 'error')
      setStarting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-[14px] font-semibold text-gray-900">{label}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <p className="text-[12px] text-gray-500">
            {t('infra.installDesc', { service: label })}
          </p>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('infra.targetNode')}</label>
            <select
              value={selectedNode}
              onChange={(e) => handleNodeChange(e.target.value)}
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand"
            >
              <option value="">{t('infra.selectNode')}</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} — {n.ip} ({n.os_name || n.os_family || 'Unknown OS'})
                </option>
              ))}
            </select>
          </div>
          {nodes.length === 0 && (
            <p className="text-[11px] text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
              {t('infra.noNodes')}
            </p>
          )}
          {checkingPlatform && (
            <div className="flex items-center gap-2 text-[11px] text-gray-400">
              <Spinner size={11} /> {t('infra.checkingPlatform')}
            </div>
          )}
          {platformCheck && !platformCheck.has_tarball && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 space-y-2">
              <p className="text-[12px] font-semibold text-amber-800">
                {t('infra.platformMissingTitle', { platform: platformCheck.platform })}
              </p>
              <p className="text-[11px] text-amber-700">{t('infra.platformMissingDesc')}</p>
              <ul className="text-[11px] text-amber-700 space-y-2">
                <li>
                  <span className="font-semibold">{t('infra.platformOptionInternet')}</span>
                  {' '}{t('infra.platformOptionInternetDesc')}
                </li>
                <li>
                  <span className="font-semibold">{t('infra.platformOptionTarball')}</span>
                  {' '}{t('infra.platformOptionTarballDesc')}
                  <code className="block mt-1 px-2 py-1 bg-amber-100 rounded font-mono text-[10px] break-all">
                    {platformCheck.packages_dir}/{platformCheck.tarball_name}
                  </code>
                </li>
              </ul>
              <p className="text-[11px] text-amber-600 italic">{t('infra.platformContinueAnyway')}</p>
            </div>
          )}
          {platformCheck?.has_tarball && (
            <p className="text-[11px] text-green-700 bg-green-50 rounded-lg px-3 py-2">
              {t('infra.platformReady', { platform: platformCheck.platform })}
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className={btn(false)}>{t('common.cancel')}</button>
          <button onClick={handleStart} disabled={!selectedNode || starting} className={btn(true)}>
            {starting && <Spinner size={13} />}
            {starting ? t('infra.starting') : t('infra.startInstall')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tab 1: Masters & Managers ─────────────────────────────────────────────────

function MasterCard({ service, status, nodes, onJobStarted, t }) {
  const [showConnect, setShowConnect]     = useState(false)
  const [showInstall, setShowInstall]     = useState(false)
  const [showMigrateCA, setShowMigrateCA] = useState(false)
  const isPuppet      = service === 'puppet'
  const masterService = isPuppet ? 'puppet-master' : 'wazuh-manager'
  const isEnterprise  = isPuppet && status?.edition === 'enterprise'

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center">
              <Cpu size={16} className={status?.reachable ? 'text-brand' : 'text-gray-300'} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-[14px] font-semibold text-gray-900">
                  {isPuppet ? t('infra.puppetMaster') : t('infra.wazuhManager')}
                </h3>
                {isPuppet && status?.edition && (
                  <EditionBadge edition={status.edition} t={t} />
                )}
              </div>
              <p className="text-[11px] text-gray-400">
                {isPuppet ? t('infra.puppetDesc') : t('infra.wazuhDesc')}
              </p>
            </div>
          </div>
          <StatusBadge configured={status?.configured} reachable={status?.reachable} t={t} />
        </div>

        {status?.host && (
          <div className="mb-4 px-3 py-2 bg-gray-50 rounded-lg">
            <p className="text-[11px] text-gray-400 mb-0.5">{t('infra.host')}</p>
            <p className="text-[12px] font-mono text-gray-700">{status.host}:{status.port}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { setShowConnect(!showConnect); setShowInstall(false) }}
            className={btnSm(false)}
          >
            <Link size={11} />
            {status?.configured ? t('infra.changeHost') : t('infra.connectExisting')}
          </button>
          <button
            onClick={() => { setShowInstall(true); setShowConnect(false) }}
            className={btnSm(status?.configured ? false : true)}
          >
            <Server size={11} />
            {t('infra.installOnNode')}
          </button>
          {isEnterprise && (
            <button
              onClick={() => { setShowMigrateCA(true); setShowConnect(false); setShowInstall(false) }}
              className={btnSm(false)}
            >
              {t('infra.migrateCaBtn')}
            </button>
          )}
        </div>

        {showConnect && (
          <ConnectForm
            service={service}
            onSave={() => { setShowConnect(false) }}
            onCancel={() => setShowConnect(false)}
            t={t}
          />
        )}
      </div>

      {showInstall && (
        <InstallModal
          service={masterService}
          nodes={nodes}
          onClose={() => setShowInstall(false)}
          onJobStarted={(job) => { setShowInstall(false); onJobStarted(job) }}
          t={t}
        />
      )}

      {showMigrateCA && (
        <MigrateCAModal
          onClose={() => setShowMigrateCA(false)}
          onJobStarted={(job) => { onJobStarted(job) }}
          t={t}
        />
      )}
    </>
  )
}

function MastersTab({ status, nodes, onRefresh, t }) {
  const [activeJob, setActiveJob] = useState(null)

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MasterCard
          service="puppet"
          status={status?.puppet}
          nodes={nodes}
          onJobStarted={(job) => { setActiveJob(job); setTimeout(onRefresh, 8000) }}
          t={t}
        />
        <MasterCard
          service="wazuh"
          status={status?.wazuh}
          nodes={nodes}
          onJobStarted={(job) => { setActiveJob(job); setTimeout(onRefresh, 8000) }}
          t={t}
        />
      </div>

      <div className="mt-4 p-4 bg-blue-50 border border-blue-100 rounded-xl">
        <div className="flex items-start gap-3">
          <AlertTriangle size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[12px] font-medium text-blue-800">{t('infra.mastersFirst')}</p>
            <p className="text-[11px] text-blue-600 mt-0.5">{t('infra.mastersFirstDesc')}</p>
          </div>
        </div>
      </div>

      {activeJob && (
        <LogDrawer job={activeJob} onClose={() => { setActiveJob(null); onRefresh() }} t={t} />
      )}
    </>
  )
}

// ── Tab 2: Agents ─────────────────────────────────────────────────────────────

function AgentsTab({ nodes, status, onRefresh, t }) {
  const [selectedNode, setSelectedNode] = useState('')
  const [agentSel, setAgentSel]         = useState({ puppet: true, wazuh: true })
  const [platformCheck, setPlatformCheck]     = useState(null)
  const [checkingPlatform, setCheckingPlatform] = useState(false)
  const [launching, setLaunching]       = useState(false)
  const [activeJob, setActiveJob]       = useState(null)
  const toast = useToast()

  const enrollable = nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned')

  async function handleNodeChange(nodeId) {
    setSelectedNode(nodeId)
    setPlatformCheck(null)
    if (!nodeId) return
    setCheckingPlatform(true)
    try {
      const result = await checkPuppetAgentPlatform(nodeId)
      setPlatformCheck(result)
    } catch (_) {}
    finally { setCheckingPlatform(false) }
  }

  function toggleAgent(key) {
    setAgentSel((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      if (!next.puppet && !next.wazuh) return prev
      return next
    })
  }

  async function handleLaunch() {
    if (!selectedNode) return
    const toInstall = [
      agentSel.puppet && 'puppet-agent',
      agentSel.wazuh  && 'wazuh-agent',
    ].filter(Boolean)
    if (!toInstall.length) return

    setLaunching(true)
    try {
      const jobs = await Promise.all(toInstall.map((svc) => installService(svc, selectedNode)))
      setActiveJob(jobs[0])
      setTimeout(onRefresh, 8000)
      toast(t('infra.launchStarted', { count: jobs.length }), 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLaunching(false)
    }
  }

  const node = nodes.find((n) => n.id === selectedNode)
  const canLaunch = !!selectedNode && (agentSel.puppet || agentSel.wazuh)

  // Per-node coverage
  const enrolled = nodes.filter((n) => n.puppet_enrolled || n.wazuh_enrolled).length

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left: Steps 1 & 2 */}
          <div className="space-y-6">
            {/* Step 1: Choose node */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-5 h-5 rounded-full bg-brand text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">1</span>
                <h4 className="text-[13px] font-semibold text-gray-800">{t('infra.stepChooseNode')}</h4>
              </div>
              <div className="relative">
                <select
                  value={selectedNode}
                  onChange={(e) => handleNodeChange(e.target.value)}
                  className="w-full appearance-none pl-3 pr-8 py-2.5 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white text-gray-700"
                >
                  <option value="">{t('infra.selectNode')}</option>
                  {enrollable.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname} — {n.ip}
                    </option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              </div>
              {enrollable.length === 0 && (
                <p className="mt-2 text-[11px] text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
                  {t('infra.noReachableNodes')}
                </p>
              )}
              {checkingPlatform && (
                <div className="flex items-center gap-2 mt-2 text-[11px] text-gray-400">
                  <Spinner size={11} /> {t('infra.checkingPlatform')}
                </div>
              )}
              {platformCheck && !platformCheck.has_tarball && (
                <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                  <p className="text-[11px] font-semibold text-amber-800">
                    {t('infra.platformMissingTitle', { platform: platformCheck.platform })}
                  </p>
                  <p className="text-[11px] text-amber-600 mt-0.5">{t('infra.platformContinueAnyway')}</p>
                </div>
              )}
              {platformCheck?.has_tarball && (
                <p className="mt-2 text-[11px] text-green-700 bg-green-50 rounded-lg px-3 py-2">
                  {t('infra.platformReady', { platform: platformCheck.platform })}
                </p>
              )}
            </div>

            {/* Step 2: Pick agents */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-5 h-5 rounded-full bg-brand text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">2</span>
                <h4 className="text-[13px] font-semibold text-gray-800">{t('infra.stepPickAgents')}</h4>
                <span className="text-[11px] text-gray-400">{t('infra.pickAgentsHint')}</span>
              </div>
              <div className="space-y-2">
                {[
                  { key: 'puppet', label: t('infra.puppetAgentLabel'), desc: t('infra.puppetAgentDesc') },
                  { key: 'wazuh',  label: t('infra.wazuhAgentLabel'),  desc: t('infra.wazuhAgentDesc')  },
                ].map(({ key, label, desc }) => (
                  <button
                    key={key}
                    onClick={() => toggleAgent(key)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors ${
                      agentSel[key]
                        ? 'border-brand bg-brand/5'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      agentSel[key] ? 'bg-brand/10' : 'bg-gray-100'
                    }`}>
                      <Cpu size={14} className={agentSel[key] ? 'text-brand' : 'text-gray-400'} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-[12px] font-semibold ${agentSel[key] ? 'text-brand' : 'text-gray-700'}`}>
                        {label}
                      </p>
                      <p className="text-[11px] text-gray-400">{desc}</p>
                    </div>
                    <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                      agentSel[key] ? 'border-brand bg-brand' : 'border-gray-300'
                    }`}>
                      {agentSel[key] && <CheckCircle size={10} className="text-white" />}
                    </div>
                  </button>
                ))}
              </div>

              <div className="flex gap-2 mt-2">
                {[
                  { label: t('infra.selectBoth'),  fn: () => setAgentSel({ puppet: true, wazuh: true }) },
                  { label: t('infra.puppetOnly'),  fn: () => setAgentSel({ puppet: true, wazuh: false }) },
                  { label: t('infra.wazuhOnly'),   fn: () => setAgentSel({ puppet: false, wazuh: true }) },
                ].map(({ label, fn }) => (
                  <button key={label} onClick={fn}
                    className="px-2 py-1 text-[11px] text-gray-500 hover:text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Step 3 launch */}
          <div className="flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-5 h-5 rounded-full bg-brand text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">3</span>
              <h4 className="text-[13px] font-semibold text-gray-800">{t('infra.stepLaunch')}</h4>
            </div>

            <div className="flex-1 bg-gray-50 rounded-xl p-4 flex flex-col gap-3">
              {!selectedNode ? (
                <p className="text-[12px] text-gray-400">{t('infra.selectNodeFirst')}</p>
              ) : (
                <>
                  <p className="text-[12px] text-gray-700 font-medium">
                    {node?.hostname} ({node?.ip})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {agentSel.puppet && (
                      <span className="px-2 py-1 text-[11px] font-medium text-brand bg-brand/10 rounded-full">
                        Puppet agent
                      </span>
                    )}
                    {agentSel.wazuh && (
                      <span className="px-2 py-1 text-[11px] font-medium text-brand bg-brand/10 rounded-full">
                        Wazuh agent
                      </span>
                    )}
                  </div>
                </>
              )}

              <div className="flex items-start gap-2 p-3 bg-white rounded-lg border border-gray-200 mt-auto">
                <AlertTriangle size={12} className="text-gray-400 mt-0.5 flex-shrink-0" />
                <p className="text-[11px] text-gray-500 leading-relaxed">{t('infra.launchHint')}</p>
              </div>

              <button
                onClick={handleLaunch}
                disabled={!canLaunch || launching}
                className={`w-full ${btn(canLaunch)} justify-center`}
              >
                {launching ? <Spinner size={13} /> : <Server size={13} />}
                {launching ? t('infra.starting') : t('infra.startInstall')}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Coverage table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h4 className="text-[13px] font-semibold text-gray-800">{t('infra.agentCoverage')}</h4>
          <span className="text-[11px] text-gray-400">
            {enrolled} / {nodes.length} {t('infra.agentCoverageCount')}
          </span>
        </div>
        {nodes.length === 0 ? (
          <p className="text-[12px] text-gray-400 text-center py-8">{t('infra.noNodes')}</p>
        ) : (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colNode')}</th>
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colPuppetAgent')}</th>
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colWazuhAgent')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr key={n.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800">{n.hostname}</p>
                    <p className="text-[11px] text-gray-400 font-mono">{n.ip}</p>
                  </td>
                  <td className="px-5 py-3">
                    <Pip
                      ok={n.puppet_enrolled || false}
                      label={n.puppet_enrolled ? t('infra.enrolled') : t('infra.notEnrolled')}
                      tooltip={n.puppet_enrolled && status?.puppet?.edition === 'community' ? t('infra.puppetCaTooltip') : undefined}
                    />
                  </td>
                  <td className="px-5 py-3">
                    <Pip ok={n.wazuh_enrolled || false} label={n.wazuh_enrolled ? t('infra.enrolled') : t('infra.notEnrolled')} />
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => { setSelectedNode(n.id); handleNodeChange(n.id) }}
                      className={btnSm(false)}
                    >
                      {t('infra.enroll')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {activeJob && (
        <LogDrawer job={activeJob} onClose={() => { setActiveJob(null); onRefresh() }} t={t} />
      )}
    </>
  )
}

// ── Tab 3: Verification (InSpec) ──────────────────────────────────────────────

function VerifyTab({ nodes, onRefresh, t }) {
  const [status, setStatus]       = useState(null)
  const [loading, setLoading]     = useState(true)
  const [installing, setInstalling] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [probing, setProbing]     = useState({})
  const [results, setResults]     = useState(null)
  const toast = useToast()

  async function loadStatus() {
    try {
      setStatus(await getInspecStatus())
    } catch (_) {
      setStatus({ installed: false, version: null })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStatus() }, [])

  async function handleInstall() {
    setInstalling(true)
    try {
      const res = await installInspecOnController()
      toast(t('infra.inspecInstallDone', { version: res.version || '' }), 'success')
      await loadStatus()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setInstalling(false)
    }
  }

  async function handleVerifyAll() {
    setVerifying(true)
    setResults(null)
    try {
      const res = await verifyInspecAllNodes()
      setResults(res)
      toast(t('infra.inspecVerifyDone', { ok: res.reachable, total: res.total }), 'success')
      onRefresh?.()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setVerifying(false)
    }
  }

  async function handleProbeNode(nodeId) {
    setProbing((p) => ({ ...p, [nodeId]: true }))
    try {
      await verifyInspecNode(nodeId)
      onRefresh?.()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setProbing((p) => ({ ...p, [nodeId]: false }))
    }
  }

  const reachableCount = nodes.filter((n) => n.inspec_installed).length

  return (
    <>
      {/* InSpec info card */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center">
              <ShieldCheck size={16} className={status?.installed ? 'text-brand' : 'text-gray-300'} />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-gray-900">{t('infra.inspec')}</h3>
              <p className="text-[11px] text-gray-400">{t('infra.inspecDesc')}</p>
            </div>
          </div>
          {loading ? (
            <Spinner size={12} />
          ) : status?.installed ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-50 text-green-700">
              <CheckCircle size={9} /> {t('infra.inspecInstalled')}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-500">
              {t('infra.inspecMissing')}
            </span>
          )}
        </div>

        <p className="text-[12px] text-gray-500 mb-4 leading-relaxed">{t('infra.inspecExplain')}</p>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="px-3 py-2 bg-gray-50 rounded-lg">
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{t('infra.inspecPlatformVersion')}</p>
            <p className="text-[12px] font-mono text-gray-700">
              {status?.installed ? (status.version || 'installed') : t('infra.inspecMissing')}
            </p>
          </div>
          <div className="px-3 py-2 bg-gray-50 rounded-lg">
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{t('infra.inspecCoverage')}</p>
            <p className="text-[12px] font-mono text-gray-700">
              {reachableCount} / {nodes.length} {t('infra.inspecNodesReachable')}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {!status?.installed && (
            <button onClick={handleInstall} disabled={installing} className={btnSm(true)}>
              {installing ? <Spinner size={11} /> : <Server size={11} />}
              {installing ? t('infra.inspecInstalling') : t('infra.inspecInstallBtn')}
            </button>
          )}
          <button
            onClick={handleVerifyAll}
            disabled={!status?.installed || verifying || nodes.length === 0}
            className={btnSm(status?.installed)}
          >
            {verifying ? <Spinner size={11} /> : <RefreshCw size={11} />}
            {verifying ? t('infra.inspecVerifying') : t('infra.inspecVerifyBtn')}
          </button>
        </div>

        {results && results.results?.length > 0 && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <p className="text-[11px] font-semibold text-gray-600 uppercase tracking-wider mb-2">
              {t('infra.inspecLastVerify')}
            </p>
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {results.results.map((r) => (
                <div key={r.node_id || r.hostname} className="flex items-start gap-2 text-[11px]">
                  {r.reachable ? (
                    <CheckCircle size={11} className="text-green-500 mt-0.5 flex-shrink-0" />
                  ) : (
                    <XCircle size={11} className="text-red-500 mt-0.5 flex-shrink-0" />
                  )}
                  <span className="font-mono text-gray-700">{r.hostname || r.node_id?.slice(0, 8)}</span>
                  {!r.reachable && r.output && (
                    <span className="text-red-600 truncate" title={r.output}>
                      — {r.output.split('\n').slice(-1).join(' ').slice(0, 60)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Per-node table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <h4 className="text-[13px] font-semibold text-gray-800">{t('infra.nodeInspection')}</h4>
          <span className="text-[11px] text-gray-400">
            {reachableCount} / {nodes.length} {t('infra.inspecNodesReachable')}
          </span>
        </div>
        {nodes.length === 0 ? (
          <p className="text-[12px] text-gray-400 text-center py-8">{t('infra.noNodes')}</p>
        ) : (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colNode')}</th>
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colSshReach')}</th>
                <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('infra.colLastProbe')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr key={n.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <p className="font-medium text-gray-800">{n.hostname}</p>
                    <p className="text-[11px] text-gray-400 font-mono">{n.ip}</p>
                  </td>
                  <td className="px-5 py-3">
                    <Pip ok={n.inspec_installed || false} label={n.inspec_installed ? t('infra.reachable') : t('infra.unreachable')} />
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {timeAgo(n.updated_at)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleProbeNode(n.id)}
                      disabled={!status?.installed || probing[n.id]}
                      className={btnSm(false)}
                    >
                      {probing[n.id] ? <Spinner size={11} /> : <Search size={11} />}
                      {t('infra.inspect')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function InfrastructurePage() {
  const t = useT()
  const [status, setStatus]     = useState(null)
  const [nodes, setNodes]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [activeTab, setActiveTab]   = useState('masters')

  async function load() {
    try {
      const [s, n] = await Promise.all([getInfrastructureStatus(), listNodes()])
      setStatus(s)
      setNodes(n)
    } catch (_) {}
    finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { load() }, [])

  function handleRefresh() {
    setRefreshing(true)
    load()
  }

  const enrolledCount = nodes.filter((n) => n.puppet_enrolled || n.wazuh_enrolled).length

  const TABS = [
    { key: 'masters', label: t('infra.tabMasters') },
    { key: 'agents',  label: t('infra.tabAgents'),  pill: `${enrolledCount}/${nodes.length}` },
    { key: 'verify',  label: t('infra.tabVerify') },
  ]

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900">{t('infra.title')}</h2>
          <p className="text-[12px] text-gray-400 mt-0.5">{t('infra.subtitle')}</p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className={btnSm(false)}>
          {refreshing ? <Spinner size={11} /> : <RefreshCw size={11} />}
          {t('common.refresh')}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-5 border-b border-gray-200 -mx-0.5 px-0.5">
        {TABS.map(({ key, label, pill }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors -mb-px ${
              activeTab === key
                ? 'border-brand text-brand'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
            {pill && (
              <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-full ${
                activeTab === key ? 'bg-brand/10 text-brand' : 'bg-gray-100 text-gray-500'
              }`}>
                {pill}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {activeTab === 'masters' && (
            <MastersTab status={status} nodes={nodes} onRefresh={handleRefresh} t={t} />
          )}
          {activeTab === 'agents' && (
            <AgentsTab nodes={nodes} status={status} onRefresh={handleRefresh} t={t} />
          )}
          {activeTab === 'verify' && (
            <VerifyTab nodes={nodes} onRefresh={handleRefresh} t={t} />
          )}
        </>
      )}

      {/* Preflight info (always visible) */}
      {!loading && (
        <div className="mt-6 p-4 bg-white border border-gray-100 rounded-xl">
          <p className="text-[12px] font-semibold text-gray-800 mb-3">{t('infra.preflightTitle')}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
            {[
              'preflightTime', 'preflightReach', 'preflightDns',
              'preflightClone', 'preflightResources', 'preflightAirgap',
            ].map((key) => (
              <div key={key} className="flex items-start gap-2">
                <CheckCircle size={13} className="text-green-500 mt-0.5 flex-shrink-0" />
                <p className="text-[11px] text-gray-600 leading-snug">{t(`infra.${key}`)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
