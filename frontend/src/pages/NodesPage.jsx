import { useState } from 'react'
import { AlertTriangle, RefreshCw, Server, Trash2, Wifi } from 'lucide-react'
import { deleteNode, listNodes, pingAllNodes, pingNode } from '../lib/api.js'
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

export default function NodesPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('')
  const [osFamilyFilter, setOsFamilyFilter] = useState('')
  const [pingingAll, setPingingAll] = useState(false)
  const [pingingIds, setPingingIds] = useState(new Map())
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

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
          {/* Filters */}
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
          {/* Actions */}
          <button
            onClick={handlePingAll}
            disabled={pingingAll}
            className={btnSm(false)}
          >
            {pingingAll ? <Spinner size={11} /> : <Wifi size={11} />}
            Ping All
          </button>
          <button onClick={refetch} className={btnSm(false)}>
            <RefreshCw size={11} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-[12px] text-red-600">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading && <Skeleton />}

        {!loading && nodes && nodes.length === 0 && (
          <EmptyState
            icon={Server}
            title="No nodes registered"
            description="Go to Add VM to register your first server"
          />
        )}

        {!loading && nodes && nodes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  {['Status', 'Hostname', 'IP Address', 'OS', 'SSH Port', 'Puppet', 'Wazuh', 'Last Seen', 'Actions'].map((h) => (
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
                        <div className="flex items-center gap-1 mt-0.5">
                          <AlertTriangle size={10} className="text-amber-500 flex-shrink-0" />
                          <span className="text-[10px] text-amber-600 font-medium">DNS not resolving</span>
                        </div>
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
          {nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned').length} reachable
        </p>
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
