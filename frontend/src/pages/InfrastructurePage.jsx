import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Cpu, Link, RefreshCw, Server, ShieldCheck, XCircle } from 'lucide-react'
import {
  getInfrastructureStatus, installService, listNodes,
  setPuppetMasterHost, setWazuhManagerHost, jobWsUrl,
  checkPuppetAgentPlatform,
  getInspecStatus, installInspecOnController, verifyInspecAllNodes,
} from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, btnSm, logLineClass } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

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

function LogDrawer({ job, onClose, t }) {
  const [lines, setLines] = useState([])
  const [done, setDone] = useState(false)
  const bottomRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!job) return
    const ws = new WebSocket(jobWsUrl(job.id))
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      setLines((prev) => [...prev, msg])
      if (msg.level === 'system') setDone(true)
    }
    ws.onerror = () => setDone(true)
    ws.onclose = () => setDone(true)

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
            <div key={i} className={logLineClass(l)}>
              {l.line || ' '}
            </div>
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

  const label = service === 'puppet' ? t('infra.connectToPuppet') : t('infra.connectToWazuh')
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

function InstallModal({ service, nodes, onClose, onJobStarted, t }) {
  const [selectedNode, setSelectedNode] = useState('')
  const [starting, setStarting] = useState(false)
  const [platformCheck, setPlatformCheck] = useState(null)
  const [checkingPlatform, setCheckingPlatform] = useState(false)
  const toast = useToast()

  const isAgentInstall = service === 'puppet-agent' || service === 'wazuh-agent'

  const serviceLabels = {
    'puppet-master': t('infra.installPuppetMaster'),
    'wazuh-manager': t('infra.installWazuhManager'),
    'puppet-agent':  t('infra.installPuppetAgentTitle'),
    'wazuh-agent':   t('infra.installWazuhAgentTitle'),
  }

  async function handleNodeChange(nodeId) {
    setSelectedNode(nodeId)
    setPlatformCheck(null)
    if (!nodeId || !isAgentInstall) return
    setCheckingPlatform(true)
    try {
      const result = await checkPuppetAgentPlatform(nodeId)
      setPlatformCheck(result)
    } catch (_) {
    } finally {
      setCheckingPlatform(false)
    }
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

  const label = serviceLabels[service] || service

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
              <ul className="text-[11px] text-amber-700 space-y-2 mt-1">
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
          {platformCheck && platformCheck.has_tarball && (
            <p className="text-[11px] text-green-700 bg-green-50 rounded-lg px-3 py-2">
              {t('infra.platformReady', { platform: platformCheck.platform })}
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className={btn(false)}>{t('common.cancel')}</button>
          <button
            onClick={handleStart}
            disabled={!selectedNode || starting}
            className={btn(true)}
          >
            {starting && <Spinner size={13} />}
            {starting ? t('infra.starting') : t('infra.startInstall')}
          </button>
        </div>
      </div>
    </div>
  )
}

function ServiceCard({ service, status, nodes, onStatusRefresh, t }) {
  const [showConnect, setShowConnect] = useState(false)
  const [showInstall, setShowInstall] = useState(false)
  const [showAgentInstall, setShowAgentInstall] = useState(null)
  const [activeJob, setActiveJob] = useState(null)

  const isPuppet = service === 'puppet'
  const agentService = isPuppet ? 'puppet-agent' : 'wazuh-agent'
  const masterService = isPuppet ? 'puppet-master' : 'wazuh-manager'

  function handleJobStarted(job) {
    setActiveJob(job)
    setTimeout(onStatusRefresh, 8000)
  }

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center">
              <Cpu size={16} className={status?.reachable ? 'text-brand' : 'text-gray-300'} />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-gray-900">
                {isPuppet ? t('infra.puppetMaster') : t('infra.wazuhManager')}
              </h3>
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
          {status?.reachable && (
            <button
              onClick={() => setShowAgentInstall(agentService)}
              className={btnSm(false)}
            >
              {isPuppet ? t('infra.installPuppetAgent') : t('infra.installWazuhAgent')}
            </button>
          )}
        </div>

        {showConnect && (
          <ConnectForm
            service={service}
            onSave={() => { setShowConnect(false); onStatusRefresh() }}
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
          onJobStarted={handleJobStarted}
          t={t}
        />
      )}
      {showAgentInstall && (
        <InstallModal
          service={showAgentInstall}
          nodes={nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned')}
          onClose={() => setShowAgentInstall(null)}
          onJobStarted={(job) => { setActiveJob(job); setShowAgentInstall(null) }}
          t={t}
        />
      )}
      {activeJob && (
        <LogDrawer
          job={activeJob}
          onClose={() => { setActiveJob(null); onStatusRefresh() }}
          t={t}
        />
      )}
    </>
  )
}

function InspecCard({ nodes, onNodesRefresh, t }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [results, setResults] = useState(null)
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

  async function handleVerify() {
    setVerifying(true)
    setResults(null)
    try {
      const res = await verifyInspecAllNodes()
      setResults(res)
      toast(t('infra.inspecVerifyDone', { ok: res.reachable, total: res.total }), 'success')
      onNodesRefresh?.()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setVerifying(false)
    }
  }

  const installedCount = nodes.filter((n) => n.inspec_installed).length

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
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

      <p className="text-[11px] text-gray-500 mb-4 leading-relaxed">{t('infra.inspecExplain')}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <div className="px-3 py-2 bg-gray-50 rounded-lg">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{t('infra.inspecPlatformVersion')}</p>
          <p className="text-[12px] font-mono text-gray-700">
            {status?.installed ? status.version : t('infra.inspecNotInstalled')}
          </p>
        </div>
        <div className="px-3 py-2 bg-gray-50 rounded-lg">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">{t('infra.inspecCoverage')}</p>
          <p className="text-[12px] font-mono text-gray-700">
            {installedCount} / {nodes.length} {t('infra.inspecNodesReachable')}
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
          onClick={handleVerify}
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
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
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
                    — {r.output.split('\n').slice(-2).join(' ').slice(0, 80)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function InfrastructurePage() {
  const t = useT()
  const [status, setStatus] = useState(null)
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

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

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900">{t('infra.title')}</h2>
          <p className="text-[12px] text-gray-400 mt-0.5">{t('infra.subtitle')}</p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className={btnSm(false)}>
          {refreshing ? <Spinner size={11} /> : <RefreshCw size={11} />}
          {t('common.refresh')}
        </button>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ServiceCard
            service="puppet"
            status={status?.puppet}
            nodes={nodes}
            onStatusRefresh={handleRefresh}
            t={t}
          />
          <ServiceCard
            service="wazuh"
            status={status?.wazuh}
            nodes={nodes}
            onStatusRefresh={handleRefresh}
            t={t}
          />
        </div>
      )}

      {!loading && (
        <div className="mt-4">
          <InspecCard nodes={nodes} onNodesRefresh={handleRefresh} t={t} />
        </div>
      )}

      <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-xl">
        <div className="flex items-start gap-3">
          <AlertTriangle size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="space-y-1">
            <p className="text-[12px] font-medium text-blue-800">{t('infra.infoTitle')}</p>
            <p className="text-[11px] text-blue-600">{t('infra.infoDesc')}</p>
          </div>
        </div>
      </div>

      {/* What the installer checks and self-heals automatically */}
      <div className="mt-4 p-4 bg-white border border-gray-100 rounded-xl">
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
    </div>
  )
}
