import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ChevronRight, RefreshCw, Server, Trash2, Wifi } from 'lucide-react'
import { deleteNode, listNodes, pingAllNodes, pingNode } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge, btnSm } from '../lib/tw.js'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import Spinner from '../components/common/Spinner.jsx'
import StatusDot from '../components/common/StatusDot.jsx'
import DnsModal from '../components/nodes/DnsModal.jsx'

function Skeleton() {
  return (
    <div className="space-y-2 p-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-12 rounded-lg bg-gray-100 animate-pulse" />
      ))}
    </div>
  )
}

function relativeTime(iso, t) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return t('common.justNow')
  const m = Math.floor(s / 60)
  if (m < 60) return t('common.minutesAgo', { n: m })
  const h = Math.floor(m / 60)
  if (h < 24) return t('common.hoursAgo', { n: h })
  return new Date(iso).toLocaleDateString()
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function NodesPage() {
  const t = useT()
  const toast = useToast()
  const navigate = useNavigate()
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
      toast(
        t('nodes.pingedSummary', { total: result.total, reachable: result.reachable, unreachable: result.unreachable }),
        'info'
      )
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
      toast(
        result.reachable
          ? t('nodes.pingResult', { hostname: node.hostname, ms: result.latency_ms })
          : t('nodes.pingFailed', { hostname: node.hostname }),
        result.reachable ? 'success' : 'warning'
      )
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
      toast(t('nodes.deleted', { hostname: deleteTarget.hostname }), 'success')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  const tableHeaders = [
    t('nodes.colStatus'),
    t('nodes.colHostname'),
    t('nodes.colIp'),
    t('nodes.colOs'),
    t('nodes.colSshPort'),
    t('nodes.colPuppet'),
    t('nodes.colWazuh'),
    t('nodes.colLastSeen'),
    t('nodes.colActions'),
  ]

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('nodes.title')}</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] border border-gray-200 rounded-lg px-3 py-2 bg-white outline-none focus:border-brand"
          >
            <option value="">{t('nodes.allStatuses')}</option>
            <option value="registered">{t('nodes.registered')}</option>
            <option value="reachable">{t('nodes.reachable')}</option>
            <option value="unreachable">{t('nodes.unreachable')}</option>
            <option value="provisioned">{t('nodes.provisioned')}</option>
          </select>
          <select
            value={osFamilyFilter}
            onChange={(e) => setOsFamilyFilter(e.target.value)}
            className="text-[12px] border border-gray-200 rounded-lg px-3 py-2 bg-white outline-none focus:border-brand"
          >
            <option value="">{t('nodes.allOsFamilies')}</option>
            <option value="RedHat">RedHat</option>
            <option value="Debian">Debian</option>
          </select>
          <button onClick={handlePingAll} disabled={pingingAll} className={btnSm(false)}>
            {pingingAll ? <Spinner size={11} /> : <Wifi size={11} />}
            {t('nodes.pingAll')}
          </button>
          <button onClick={refetch} className={btnSm(false)}>
            <RefreshCw size={11} />
            {t('common.refresh')}
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
          <EmptyState icon={Server} title={t('nodes.noNodes')} description={t('nodes.noNodesDesc')} />
        )}

        {!loading && nodes && nodes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  {tableHeaders.map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {nodes.map((node) => (
                  <tr
                    key={node.id}
                    onClick={() => navigate(`/nodes/${node.id}`)}
                    className="hover:bg-gray-50/50 transition-colors cursor-pointer"
                  >
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
                          onClick={(e) => { e.stopPropagation(); setDnsNode(node) }}
                          className="flex items-center gap-1 mt-0.5 hover:opacity-75 transition-opacity"
                          title={t('nodes.dnsIssue')}
                        >
                          <AlertTriangle size={10} className="text-amber-500 flex-shrink-0" />
                          <span className="text-[10px] text-amber-600 font-medium underline decoration-dotted">
                            {t('nodes.dnsIssue')}
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
                        {node.puppet_enrolled ? t('common.enrolled') : t('common.notEnrolled')}
                      </span>
                    </td>

                    {/* Wazuh */}
                    <td className="px-4 py-3">
                      <span className={badge(node.wazuh_enrolled ? 'success' : 'gray')}>
                        {node.wazuh_enrolled ? t('common.enrolled') : t('common.notEnrolled')}
                      </span>
                    </td>

                    {/* Last Seen */}
                    <td className="px-4 py-3 text-[12px] text-gray-400 whitespace-nowrap">
                      {relativeTime(node.last_seen, t)}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); handlePing(node) }}
                          disabled={pingingIds.get(node.id)}
                          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-brand transition-colors disabled:opacity-50"
                          title={t('nodes.pingAll')}
                        >
                          {pingingIds.get(node.id) ? <Spinner size={12} /> : <Wifi size={12} />}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setDnsNode(node) }}
                          className="p-1.5 rounded-md hover:bg-amber-50 text-gray-400 hover:text-amber-500 transition-colors"
                          title={t('nodes.dnsModal.title')}
                        >
                          <AlertTriangle size={12} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setDeleteTarget(node) }}
                          className="p-1.5 rounded-md hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                          title={t('nodes.deleteTitle')}
                        >
                          <Trash2 size={12} />
                        </button>
                        <ChevronRight size={14} className="text-gray-300 ml-0.5" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Summary footer */}
      {!loading && nodes && nodes.length > 0 && (
        <p className="mt-3 text-[11px] text-gray-400">
          {t('nodes.summary', {
            count: nodes.length,
            plural: nodes.length !== 1 ? 's' : '',
            reachable: nodes.filter((n) => n.status === 'reachable' || n.status === 'provisioned').length,
          })}
          {nodes.filter((n) => n.dns_resolves === false).length > 0 && (
            <span className="text-amber-500">
              {t('nodes.dnsIssues', {
                count: nodes.filter((n) => n.dns_resolves === false).length,
                plural: nodes.filter((n) => n.dns_resolves === false).length !== 1 ? 's' : '',
              })}
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
        title={t('nodes.deleteTitle')}
        message={t('nodes.deleteMsg', { hostname: deleteTarget?.hostname ?? '' })}
        confirmLabel={deleting ? t('nodes.deleting') : t('common.delete')}
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
