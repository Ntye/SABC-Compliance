import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Cpu, Link, RefreshCw, Server, XCircle } from 'lucide-react'
import {
  getInfrastructureStatus, installService, listNodes,
  setPuppetMasterHost, setWazuhManagerHost, jobWsUrl,
} from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { btn, btnSm } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ configured, reachable }) {
  if (!configured) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-500">
      Not configured
    </span>
  )
  if (reachable === null || reachable === undefined) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-600">
      Configured
    </span>
  )
  if (reachable) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-50 text-green-700">
      <CheckCircle size={9} /> Reachable
    </span>
  )
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-600">
      <XCircle size={9} /> Unreachable
    </span>
  )
}

// ── Live log drawer ───────────────────────────────────────────────────────────

function LogDrawer({ job, onClose }) {
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
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            {!done && <Spinner size={12} className="text-console-accent" />}
            {done && <CheckCircle size={13} className="text-green-400" />}
            <span className="text-[12px] font-medium text-console-text">
              Job {job.id.slice(0, 8)} — {done ? 'completed' : 'running…'}
            </span>
          </div>
          <button onClick={onClose} className="text-console-muted hover:text-console-text text-[18px] leading-none">&times;</button>
        </div>
        {/* Log output */}
        <div className="h-80 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed">
          {lines.map((l, i) => (
            <div
              key={i}
              className={
                l.level === 'system'
                  ? 'text-console-accent font-semibold mt-1'
                  : l.line.includes('FATAL') || l.line.includes('ERROR')
                  ? 'text-red-400'
                  : l.line.includes('ok:') || l.line.includes('PLAY RECAP')
                  ? 'text-green-400'
                  : l.line.startsWith('TASK') || l.line.startsWith('PLAY')
                  ? 'text-console-text font-semibold'
                  : 'text-console-muted'
              }
            >
              {l.line || ' '}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        {done && (
          <div className="px-5 py-3 border-t border-white/10 flex justify-end">
            <button onClick={onClose} className={btnSm(true)}>Close</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Connect form ──────────────────────────────────────────────────────────────

function ConnectForm({ service, onSave, onCancel }) {
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
          ? `Connected to ${result.host} (port ${result.port})`
          : `Host saved but port ${result.port} is not reachable — check firewall`,
        result.reachable ? 'success' : 'warning',
      )
      onSave()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-200 space-y-3">
      <p className="text-[11px] font-semibold text-gray-600 uppercase tracking-wider">Connect to existing {service === 'puppet' ? 'Puppet master' : 'Wazuh manager'}</p>
      <div className="flex gap-2">
        <input
          autoFocus
          value={host}
          onChange={(e) => setHost(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          placeholder={service === 'puppet' ? 'puppet.example.com' : 'wazuh.example.com'}
          className="flex-1 px-3 py-2 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
        <button onClick={handleSave} disabled={saving || !host.trim()} className={btn(true)}>
          {saving && <Spinner size={13} />}
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel} className={btn(false)}>Cancel</button>
      </div>
    </div>
  )
}

// ── Install modal ─────────────────────────────────────────────────────────────

function InstallModal({ service, nodes, onClose, onJobStarted }) {
  const [selectedNode, setSelectedNode] = useState('')
  const [starting, setStarting] = useState(false)
  const toast = useToast()

  const serviceLabels = {
    'puppet-master': 'Puppet master',
    'wazuh-manager': 'Wazuh manager',
    'puppet-agent': 'Puppet agent',
    'wazuh-agent': 'Wazuh agent',
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
          <h3 className="text-[14px] font-semibold text-gray-900">Install {serviceLabels[service]}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <p className="text-[12px] text-gray-500">
            Select a registered node to install {serviceLabels[service]} on.
            The platform will run an Ansible playbook and stream the logs live.
          </p>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1.5">Target node</label>
            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand"
            >
              <option value="">Select a node…</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} — {n.ip} ({n.os_name || n.os_family || 'Unknown OS'})
                </option>
              ))}
            </select>
          </div>
          {nodes.length === 0 && (
            <p className="text-[11px] text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
              No nodes registered. Register a server in Node Registry first.
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className={btn(false)}>Cancel</button>
          <button
            onClick={handleStart}
            disabled={!selectedNode || starting}
            className={btn(true)}
          >
            {starting && <Spinner size={13} />}
            {starting ? 'Starting…' : 'Start installation'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Service card ──────────────────────────────────────────────────────────────

function ServiceCard({ service, status, nodes, onStatusRefresh }) {
  const [showConnect, setShowConnect] = useState(false)
  const [showInstall, setShowInstall] = useState(false)
  const [showAgentInstall, setShowAgentInstall] = useState(null) // 'puppet-agent' | 'wazuh-agent'
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
        {/* Card header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center">
              <Cpu size={16} className={status?.reachable ? 'text-brand' : 'text-gray-300'} />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-gray-900">
                {isPuppet ? 'Puppet Master' : 'Wazuh Manager'}
              </h3>
              <p className="text-[11px] text-gray-400">
                {isPuppet ? 'Configuration management & compliance enforcement' : 'Security monitoring & threat detection'}
              </p>
            </div>
          </div>
          <StatusBadge configured={status?.configured} reachable={status?.reachable} />
        </div>

        {/* Host info */}
        {status?.host && (
          <div className="mb-4 px-3 py-2 bg-gray-50 rounded-lg">
            <p className="text-[11px] text-gray-400 mb-0.5">Host</p>
            <p className="text-[12px] font-mono text-gray-700">{status.host}:{status.port}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => { setShowConnect(!showConnect); setShowInstall(false) }}
            className={btnSm(false)}
          >
            <Link size={11} />
            {status?.configured ? 'Change host' : 'Connect existing'}
          </button>
          <button
            onClick={() => { setShowInstall(true); setShowConnect(false) }}
            className={btnSm(status?.configured ? false : true)}
          >
            <Server size={11} />
            Install on a node
          </button>
          {status?.reachable && (
            <button
              onClick={() => setShowAgentInstall(agentService)}
              className={btnSm(false)}
            >
              Install {isPuppet ? 'Puppet' : 'Wazuh'} agent on node
            </button>
          )}
        </div>

        {showConnect && (
          <ConnectForm
            service={service}
            onSave={() => { setShowConnect(false); onStatusRefresh() }}
            onCancel={() => setShowConnect(false)}
          />
        )}
      </div>

      {showInstall && (
        <InstallModal
          service={masterService}
          nodes={nodes}
          onClose={() => setShowInstall(false)}
          onJobStarted={handleJobStarted}
        />
      )}
      {showAgentInstall && (
        <InstallModal
          service={showAgentInstall}
          nodes={nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned')}
          onClose={() => setShowAgentInstall(null)}
          onJobStarted={(job) => { setActiveJob(job); setShowAgentInstall(null) }}
        />
      )}
      {activeJob && (
        <LogDrawer
          job={activeJob}
          onClose={() => { setActiveJob(null); onStatusRefresh() }}
        />
      )}
    </>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function InfrastructurePage() {
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
          <h2 className="text-[18px] font-semibold text-gray-900">Infrastructure</h2>
          <p className="text-[12px] text-gray-400 mt-0.5">
            Set up Puppet master and Wazuh manager before enrolling agents on nodes.
          </p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className={btnSm(false)}>
          {refreshing ? <Spinner size={11} /> : <RefreshCw size={11} />}
          Refresh
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
          />
          <ServiceCard
            service="wazuh"
            status={status?.wazuh}
            nodes={nodes}
            onStatusRefresh={handleRefresh}
          />
        </div>
      )}

      {/* Info box */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-xl">
        <div className="flex items-start gap-3">
          <AlertTriangle size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="space-y-1">
            <p className="text-[12px] font-medium text-blue-800">Before installing agents</p>
            <p className="text-[11px] text-blue-600">
              Ensure DNS resolves correctly between all nodes and the masters.
              Use the DNS check (⚠ button in Node Registry) to verify each node before enrolling agents.
              All nodes must be reachable (green status) before agent installation.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
