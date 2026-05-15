import { useState } from 'react'
import { AlertTriangle, CheckCircle, RefreshCw, Server, Trash2, Wifi, XCircle } from 'lucide-react'
import { checkNodeDns, deleteNode, listNodes, pingAllNodes, pingNode } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { badge, btnSm, dotColor } from '../lib/tw.js'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import Spinner from '../components/common/Spinner.jsx'
import StatusDot from '../components/common/StatusDot.jsx'

function Skeleton() {
  return (
    <div className="space-y-2 p-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-12 rounded-lg bg-gray-100 animate-pulse" />
      ))}
    </div>
  )
}

function relativeTime(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString()
}

// ── DNS Fix Modal ─────────────────────────────────────────────────────────────

function CheckRow({ label, check }) {
  const Icon = check.ok === true ? CheckCircle : check.ok === false ? XCircle : null
  const color = check.ok === true ? 'text-green-600' : check.ok === false ? 'text-red-500' : 'text-gray-400'
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-0">
      <div className={`mt-0.5 flex-shrink-0 ${color}`}>
        {Icon ? <Icon size={14} /> : <span className="text-[12px] font-mono text-gray-300">—</span>}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[12px] font-medium text-gray-800">{label}</span>
          {check.ok === null && <span className="text-[10px] text-gray-400">not configured</span>}
        </div>
        {check.to && (
          <div className="text-[11px] text-gray-400 font-mono truncate">
            {check.from_host} → {check.to}
          </div>
        )}
        <div className="text-[11px] text-gray-500 mt-0.5">{check.description}</div>
      </div>
    </div>
  )
}

function fixCommands(check, node, osFamily) {
  const isRedHat = osFamily === 'RedHat'
  const sudoTee = (file, content) =>
    `echo "${content}" | sudo tee -a ${file}`

  if (check.key === 'backend_to_node' && check.ok === false) {
    return {
      title: 'Fix: add node to the platform server\'s /etc/hosts',
      note: 'Run this on the PLATFORM SERVER (where the backend runs):',
      cmd: sudoTee('/etc/hosts', `${node.ip}  ${node.hostname}${node.fqdn && node.fqdn !== node.hostname ? '  ' + node.fqdn : ''}`),
    }
  }
  if (check.key === 'node_to_backend' && check.ok === false) {
    return {
      title: 'Fix: add platform server to node\'s /etc/hosts',
      note: 'Run this from the backend/ directory:',
      cmd: `ssh -i ./keys/ansible_id_rsa ansible@${node.ip} \\\n  "echo '$(hostname -I | awk '{print $1}')  $(hostname -f)' | sudo tee -a /etc/hosts"`,
    }
  }
  if (check.key === 'node_to_puppet' && check.ok === false && check.to) {
    return {
      title: 'Fix: add Puppet master to node\'s /etc/hosts',
      note: 'Replace <puppet-ip> with the actual IP of your Puppet master, then run from backend/:',
      cmd: `ssh -i ./keys/ansible_id_rsa ansible@${node.ip} \\\n  "echo '<puppet-ip>  ${check.to}' | sudo tee -a /etc/hosts"`,
    }
  }
  if (check.key === 'node_to_wazuh' && check.ok === false && check.to) {
    return {
      title: 'Fix: add Wazuh manager to node\'s /etc/hosts',
      note: 'Replace <wazuh-ip> with the actual IP of your Wazuh manager, then run from backend/:',
      cmd: `ssh -i ./keys/ansible_id_rsa ansible@${node.ip} \\\n  "echo '<wazuh-ip>  ${check.to}' | sudo tee -a /etc/hosts"`,
    }
  }
  return null
}

function CopyBtn({ text }) {
  const [done, setDone] = useState(false)
  async function copy() {
    await navigator.clipboard.writeText(text)
    setDone(true)
    setTimeout(() => setDone(false), 1500)
  }
  return (
    <button onClick={copy} className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-console-muted hover:text-console-text transition-colors">
      {done ? 'Copied' : 'Copy'}
    </button>
  )
}

function DnsModal({ node, onClose, onRefetch }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const data = await checkNodeDns(node.id)
      setResult(data)
      onRefetch()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const CHECK_LABELS = {
    backend_to_node: 'Platform → Node',
    node_to_backend: 'Node → Platform',
    node_to_puppet: 'Node → Puppet master',
    node_to_wazuh: 'Node → Wazuh manager',
  }

  const checks = result
    ? Object.entries(result.checks).map(([key, val]) => ({ key, ...val }))
    : []

  const failingChecks = checks.filter((c) => c.ok === false)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="text-[14px] font-semibold text-gray-900">DNS Resolution Check</h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              <span className="font-mono">{node.hostname}</span>
              {node.fqdn && node.fqdn !== node.hostname && (
                <span className="ml-1 text-gray-300">({node.fqdn})</span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {/* Run button */}
          <button
            onClick={run}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2 text-[12px] font-medium rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-60 transition-colors"
          >
            {loading && <Spinner size={12} />}
            {loading ? 'Running checks…' : result ? 'Re-run checks' : 'Run DNS checks'}
          </button>

          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          {/* Results */}
          {result && (
            <>
              <div className="rounded-xl border border-gray-100 overflow-hidden">
                {checks.map((c) => (
                  <CheckRow key={c.key} label={CHECK_LABELS[c.key] || c.key} check={c} />
                ))}
              </div>

              {result.all_ok && (
                <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-lg">
                  <CheckCircle size={13} className="text-green-600" />
                  <span className="text-[12px] text-green-700 font-medium">All DNS checks passed — ready for Puppet and Wazuh enrollment</span>
                </div>
              )}

              {/* Fix instructions for each failing check */}
              {failingChecks.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">How to fix</p>
                  {failingChecks.map((c) => {
                    const fix = fixCommands(c, node, node.os_family)
                    if (!fix) return null
                    return (
                      <div key={c.key} className="bg-console-bg rounded-xl p-4">
                        <p className="text-[11px] font-semibold text-console-text mb-1">{fix.title}</p>
                        <p className="text-[10px] text-console-muted mb-2">{fix.note}</p>
                        <div className="flex items-start justify-between gap-2">
                          <pre className="text-[11px] font-mono text-console-text whitespace-pre-wrap flex-1 leading-relaxed">{fix.cmd}</pre>
                          <CopyBtn text={fix.cmd} />
                        </div>
                      </div>
                    )
                  })}
                  <p className="text-[10px] text-gray-400">
                    After applying fixes, click <strong>Re-run checks</strong> to confirm all checks pass before enrolling agents.
                  </p>
                </div>
              )}
            </>
          )}

          {!result && !loading && (
            <p className="text-[12px] text-gray-400 text-center py-4">
              Click "Run DNS checks" to verify that the node hostname resolves correctly
              between all components — required before Puppet or Wazuh agent enrollment.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NodesPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('')
  const [osFamilyFilter, setOsFamilyFilter] = useState('')
  const [pingingAll, setPingingAll] = useState(false)
  const [pingingIds, setPingingIds] = useState(new Map())
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [dnsNode, setDnsNode] = useState(null)

  const { data: nodes, loading, error, refetch } = useApi(
    () => listNodes({ status: statusFilter || undefined, os_family: osFamilyFilter || undefined }),
    { deps: [statusFilter, osFamilyFilter] }
  )

  async function handlePingAll() {
    setPingingAll(true)
    try {
      const result = await pingAllNodes()
      toast(`Pinged ${result.total} nodes — ${result.reachable} reachable, ${result.unreachable} unreachable`, 'info')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setPingingAll(false)
    }
  }

  async function handlePing(node) {
    setPingingIds((prev) => new Map(prev).set(node.id, true))
    try {
      const result = await pingNode(node.id)
      toast(result.reachable ? `${node.hostname} is reachable (${result.latency_ms}ms)` : `${node.hostname} is unreachable`, result.reachable ? 'success' : 'warning')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setPingingIds((prev) => {
        const next = new Map(prev)
        next.delete(node.id)
        return next
      })
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteNode(deleteTarget.id)
      toast(`Node '${deleteTarget.hostname}' deleted`, 'success')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-[18px] font-semibold text-gray-900">Node Registry</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] border border-gray-200 rounded-lg px-3 py-2 bg-white outline-none focus:border-brand"
          >
            <option value="">All statuses</option>
            <option value="registered">Registered</option>
            <option value="reachable">Reachable</option>
            <option value="unreachable">Unreachable</option>
            <option value="provisioned">Provisioned</option>
          </select>
          <select
            value={osFamilyFilter}
            onChange={(e) => setOsFamilyFilter(e.target.value)}
            className="text-[12px] border border-gray-200 rounded-lg px-3 py-2 bg-white outline-none focus:border-brand"
          >
            <option value="">All OS families</option>
            <option value="RedHat">RedHat</option>
            <option value="Debian">Debian</option>
          </select>
          <button onClick={handlePingAll} disabled={pingingAll} className={btnSm(false)}>
            {pingingAll ? <Spinner size={11} /> : <Wifi size={11} />}
            Ping All
          </button>
          <button onClick={refetch} className={btnSm(false)}>
            <RefreshCw size={11} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-[12px] text-red-600">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading && <Skeleton />}

        {!loading && nodes && nodes.length === 0 && (
          <EmptyState icon={Server} title="No nodes registered" description="Go to Add VM to register your first server" />
        )}

        {!loading && nodes && nodes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  {['Status', 'Hostname / FQDN', 'IP Address', 'OS', 'SSH Port', 'Puppet', 'Wazuh', 'Last Seen', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {nodes.map((node) => (
                  <tr key={node.id} className="hover:bg-gray-50/50 transition-colors">
                    {/* Status */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <StatusDot status={node.status} />
                        <span className="text-[11px] text-gray-500 capitalize">{node.status}</span>
                      </div>
                    </td>

                    {/* Hostname */}
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{node.hostname}</div>
                      {node.fqdn && node.fqdn !== node.hostname && (
                        <div className="text-[11px] font-mono text-gray-400 truncate max-w-[200px]">{node.fqdn}</div>
                      )}
                      {node.description && (
                        <div className="text-[11px] text-gray-400 truncate max-w-[200px]">{node.description}</div>
                      )}
                      {node.dns_resolves === false && (
                        <button
                          onClick={() => setDnsNode(node)}
                          className="flex items-center gap-1 mt-0.5 hover:opacity-75 transition-opacity"
                          title="Click to run DNS checks and see fix instructions"
                        >
                          <AlertTriangle size={10} className="text-amber-500 flex-shrink-0" />
                          <span className="text-[10px] text-amber-600 font-medium underline decoration-dotted">
                            DNS not resolving — click to fix
                          </span>
                        </button>
                      )}
                    </td>

                    {/* IP */}
                    <td className="px-4 py-3 font-mono text-[12px] text-gray-600">{node.ip}</td>

                    {/* OS */}
                    <td className="px-4 py-3">
                      {node.os_family ? (
                        <div className="flex flex-col gap-0.5">
                          <span className={badge(node.os_family)}>{node.os_family}</span>
                          {node.os_name && (
                            <span className="text-[10px] text-gray-400 truncate max-w-[140px]">{node.os_name}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>

                    {/* SSH Port */}
                    <td className="px-4 py-3 font-mono text-[12px] text-gray-600">{node.ssh_port}</td>

                    {/* Puppet */}
                    <td className="px-4 py-3">
                      <span className={badge(node.puppet_enrolled ? 'success' : 'gray')}>
                        {node.puppet_enrolled ? 'enrolled' : 'none'}
                      </span>
                    </td>

                    {/* Wazuh */}
                    <td className="px-4 py-3">
                      <span className={badge(node.wazuh_enrolled ? 'success' : 'gray')}>
                        {node.wazuh_enrolled ? 'enrolled' : 'none'}
                      </span>
                    </td>

                    {/* Last Seen */}
                    <td className="px-4 py-3 text-[12px] text-gray-400 whitespace-nowrap">
                      {relativeTime(node.last_seen)}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handlePing(node)}
                          disabled={pingingIds.get(node.id)}
                          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-brand transition-colors disabled:opacity-50"
                          title="Ping node"
                        >
                          {pingingIds.get(node.id) ? <Spinner size={12} /> : <Wifi size={12} />}
                        </button>
                        <button
                          onClick={() => setDnsNode(node)}
                          className="p-1.5 rounded-md hover:bg-amber-50 text-gray-400 hover:text-amber-500 transition-colors"
                          title="DNS checks"
                        >
                          <AlertTriangle size={12} />
                        </button>
                        <button
                          onClick={() => setDeleteTarget(node)}
                          className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                          title="Delete node"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Summary */}
      {!loading && nodes && nodes.length > 0 && (
        <p className="mt-3 text-[11px] text-gray-400">
          {nodes.length} node{nodes.length !== 1 ? 's' : ''} •{' '}
          {nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned').length} reachable •{' '}
          {nodes.filter((n) => n.dns_resolves === false).length > 0 && (
            <span className="text-amber-500">
              {nodes.filter((n) => n.dns_resolves === false).length} DNS issue{nodes.filter((n) => n.dns_resolves === false).length !== 1 ? 's' : ''}
            </span>
          )}
        </p>
      )}

      {dnsNode && (
        <DnsModal
          node={dnsNode}
          onClose={() => setDnsNode(null)}
          onRefetch={refetch}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete node?"
        message={`'${deleteTarget?.hostname}' will be permanently removed from the registry. This does not uninstall any agents from the server.`}
        confirmLabel={deleting ? 'Deleting…' : 'Delete'}
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
