import { useState, useMemo } from 'react'
import { Plus, Trash2, X, Search, CheckCircle, XCircle, Server } from 'lucide-react'
import { listNodeGroups, createNodeGroup, deleteNodeGroup, addNodeToGroup, listNodes } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import Spinner from '../components/common/Spinner.jsx'

function SyncIcon({ ok }) {
  return ok
    ? <CheckCircle size={14} className="text-green-500" />
    : <XCircle size={14} className="text-red-400" />
}

function Modal({ title, onClose, wide, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className={[
        'relative bg-white rounded-xl border border-gray-100 shadow-xl mx-4 p-6 overflow-y-auto max-h-[90vh]',
        wide ? 'w-full max-w-2xl' : 'w-full max-w-md',
      ].join(' ')}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-[14px] font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
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

export default function NodeGroupsPage() {
  const t = useT()
  const toast = useToast()
  const { data: groups, loading, error, refetch } = useApi(listNodeGroups)
  const { data: nodes } = useApi(listNodes)

  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Create form state
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [selectedNodeIds, setSelectedNodeIds] = useState([])
  const [nodeSearch, setNodeSearch] = useState('')

  const filtered = useMemo(() => {
    if (!groups) return []
    const q = query.toLowerCase()
    return groups.filter((g) =>
      !q || g.name.toLowerCase().includes(q) || (g.description || '').toLowerCase().includes(q)
    )
  }, [groups, query])

  const filteredNodes = useMemo(() => {
    if (!nodes) return []
    const q = nodeSearch.toLowerCase()
    if (!q) return nodes
    return nodes.filter((n) =>
      (n.hostname || '').toLowerCase().includes(q) || (n.ip || '').toLowerCase().includes(q)
    )
  }, [nodes, nodeSearch])

  function toggleNode(id) {
    setSelectedNodeIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  function resetCreateForm() {
    setNewName('')
    setNewDesc('')
    setSelectedNodeIds([])
    setNodeSearch('')
  }

  async function handleCreate(e) {
    e.preventDefault()
    if (!newName.trim()) {
      toast(t('nodeGroups.name') + ' required', 'error')
      return
    }
    setSaving(true)
    try {
      const created = await createNodeGroup({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      })
      // Add selected nodes (best-effort, non-fatal)
      if (selectedNodeIds.length > 0) {
        await Promise.allSettled(selectedNodeIds.map((nid) => addNodeToGroup(created.id, nid)))
      }
      const msgs = []
      if (created.wazuh_synced) msgs.push('Wazuh ✓')
      else msgs.push('Wazuh sync failed')
      if (created.puppet_synced) msgs.push('Puppet ✓')
      else msgs.push('Puppet sync failed')
      const allSynced = created.wazuh_synced && created.puppet_synced
      toast(`Group created — ${msgs.join(', ')}`, allSynced ? 'success' : 'warning')
      setShowCreate(false)
      resetCreateForm()
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteNodeGroup(deleteTarget.id)
      toast(`Group "${deleteTarget.name}" deleted from platform, Wazuh, and Puppet`, 'success')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('nodeGroups.title')}</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors"
        >
          <Plus size={13} />
          {t('nodeGroups.createGroup')}
        </button>
      </div>

      {/* Filter bar */}
      <div className="relative mb-4 max-w-xs">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter groups…"
          className="w-full pl-8 pr-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 bg-white"
        />
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 border border-red-200 bg-red-50 rounded-lg text-[12px] text-red-600">
          {error}
        </div>
      )}

      {/* Table */}
      {!loading && !error && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-gray-400 flex flex-col items-center gap-2">
              <Server size={28} className="text-gray-200" />
              {query ? 'No groups match your filter.' : t('nodeGroups.noGroups')}
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {t('nodeGroups.name')}
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {t('nodeGroups.description')}
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {t('nodeGroups.nodes')}
                  </th>
                  <th className="text-center px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {t('nodeGroups.wazuhSync')}
                  </th>
                  <th className="text-center px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {t('nodeGroups.puppetSync')}
                  </th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((g) => (
                  <tr key={g.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium text-gray-800">
                      <div className="flex items-center gap-2">
                        <Server size={13} className="text-gray-400 flex-shrink-0" />
                        {g.name}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-400 max-w-[200px]">
                      <span className="line-clamp-1">{g.description || '—'}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {g.node_ids?.length ?? 0}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex justify-center">
                        <SyncIcon ok={g.wazuh_synced} />
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex justify-center">
                        <SyncIcon ok={g.puppet_synced} />
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {relativeTime(g.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => setDeleteTarget(g)}
                          title="Delete group"
                          className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <Modal
          title={t('nodeGroups.createGroup')}
          onClose={() => { setShowCreate(false); resetCreateForm() }}
          wide
        >
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">
                {t('nodeGroups.name')} *
              </label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
                required
                placeholder="e.g. web-servers"
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">
                {t('nodeGroups.description')}
              </label>
              <textarea
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={2}
                placeholder="Optional description"
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 resize-none"
              />
            </div>

            {/* Node selector */}
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">
                {t('nodeGroups.selectNodes')}
              </label>
              {nodes && nodes.length > 0 ? (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="px-3 py-2 border-b border-gray-100 bg-gray-50/50">
                    <div className="flex items-center gap-2">
                      <Search size={12} className="text-gray-400 flex-shrink-0" />
                      <input
                        type="text"
                        value={nodeSearch}
                        onChange={(e) => setNodeSearch(e.target.value)}
                        placeholder="Filter nodes…"
                        className="flex-1 text-[11px] outline-none bg-transparent text-gray-700 placeholder-gray-400"
                      />
                    </div>
                  </div>
                  <div className="max-h-48 overflow-y-auto divide-y divide-gray-50">
                    {filteredNodes.length === 0 ? (
                      <p className="px-3 py-2 text-[11px] text-gray-400 italic">No nodes match.</p>
                    ) : (
                      filteredNodes.map((n) => (
                        <label
                          key={n.id}
                          className="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={selectedNodeIds.includes(n.id)}
                            onChange={() => toggleNode(n.id)}
                            className="accent-brand"
                          />
                          <span className="text-[12px] text-gray-700 font-medium">{n.hostname}</span>
                          {n.ip && (
                            <span className="text-[11px] text-gray-400">{n.ip}</span>
                          )}
                          {n.status && (
                            <span className={[
                              'ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded-full',
                              n.status === 'reachable'
                                ? 'bg-green-50 text-green-600'
                                : 'bg-gray-100 text-gray-500',
                            ].join(' ')}>
                              {n.status}
                            </span>
                          )}
                        </label>
                      ))
                    )}
                  </div>
                  {selectedNodeIds.length > 0 && (
                    <div className="px-3 py-1.5 border-t border-gray-100 bg-gray-50/50">
                      <span className="text-[10px] text-brand font-medium">
                        {selectedNodeIds.length} node{selectedNodeIds.length !== 1 ? 's' : ''} selected
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-[12px] text-gray-400 italic px-1">
                  {nodes === null ? 'Loading nodes…' : 'No nodes registered.'}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
              >
                {saving ? <Spinner size={12} /> : <Plus size={12} />}
                {saving ? 'Creating…' : t('nodeGroups.createGroup')}
              </button>
              <button
                type="button"
                onClick={() => { setShowCreate(false); resetCreateForm() }}
                className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <Modal
          title="Delete node group?"
          onClose={() => setDeleteTarget(null)}
        >
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-100 rounded-lg">
              <XCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-[12px] font-medium text-red-800 mb-0.5">
                  Deleting <span className="font-semibold">"{deleteTarget.name}"</span>
                </p>
                <p className="text-[11px] text-red-600">
                  {t('nodeGroups.deleteConfirm')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-1.5 bg-red-600 text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Spinner size={12} /> : <Trash2 size={12} />}
                {deleting ? 'Deleting…' : 'Delete group'}
              </button>
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
