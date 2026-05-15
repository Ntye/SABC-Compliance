import { useState } from 'react'
import { Copy, Plus, Trash2 } from 'lucide-react'
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  setApiKey as storeApiKey,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { badge } from '../lib/tw.js'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import Spinner from '../components/common/Spinner.jsx'

function relativeTime(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} minutes ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} hours ago`
  return new Date(iso).toLocaleDateString()
}

export default function ApiKeysPage() {
  const toast = useToast()
  const { data: keys, loading, error, refetch } = useApi(listApiKeys)

  const [name, setName] = useState('')
  const [role, setRole] = useState('readonly')
  const [creating, setCreating] = useState(false)
  const [newKey, setNewKey] = useState(null)

  const [revokeTarget, setRevokeTarget] = useState(null)
  const [revoking, setRevoking] = useState(false)

  async function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      const result = await createApiKey(name.trim(), role)
      setNewKey(result)
      setName('')
      setRole('readonly')
      refetch()
      toast('API key created', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke() {
    if (!revokeTarget) return
    setRevoking(true)
    try {
      await revokeApiKey(revokeTarget.id)
      setRevokeTarget(null)
      refetch()
      toast('API key revoked', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRevoking(false)
    }
  }

  async function copyKey(val) {
    await navigator.clipboard.writeText(val)
    toast('Copied to clipboard', 'success')
  }

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-6">API Keys</h2>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-6 max-w-lg">
        <h3 className="text-[13px] font-semibold text-gray-700 mb-4">Create new key</h3>
        <form onSubmit={handleCreate} className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. ci-pipeline"
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
            >
              <option value="readonly">readonly</option>
              <option value="operator">operator</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={creating || !name.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-[13px] font-medium rounded-lg hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {creating ? <Spinner size={13} /> : <Plus size={13} />}
            Create key
          </button>
        </form>

        {/* New key reveal */}
        {newKey && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-[11px] font-medium text-amber-800 mb-2">
              ⚠ Copy this key now — it will not be shown again
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-[12px] font-mono bg-white border border-amber-200 rounded px-2 py-1 text-amber-900 break-all">
                {newKey.api_key}
              </code>
              <button
                onClick={() => copyKey(newKey.api_key)}
                className="p-1.5 hover:bg-amber-100 rounded text-amber-700"
              >
                <Copy size={13} />
              </button>
            </div>
            <button
              onClick={() => { storeApiKey(newKey.api_key); toast('Stored as active key', 'success') }}
              className="mt-2 text-[11px] text-amber-700 hover:underline"
            >
              Use as active key
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading && (
          <div className="p-6 space-y-3">
            {[1,2,3].map(i => <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />)}
          </div>
        )}
        {error && (
          <div className="p-4 border border-red-200 bg-red-50 rounded-lg m-4">
            <p className="text-[12px] text-red-600">{error}</p>
          </div>
        )}
        {!loading && !error && keys && (
          keys.length === 0 ? (
            <EmptyState icon={Key} title="No API keys" description="Create your first key above" />
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Name</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Role</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Last used</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium">{k.name}</td>
                    <td className="px-4 py-3"><span className={badge(k.role)}>{k.role}</span></td>
                    <td className="px-4 py-3">
                      <span className={badge(k.active ? 'success' : 'gray')}>{k.active ? 'active' : 'revoked'}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-[12px]">{relativeTime(k.last_used)}</td>
                    <td className="px-4 py-3 text-gray-400 text-[12px]">{relativeTime(k.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {k.active && (
                        <button
                          onClick={() => setRevokeTarget(k)}
                          className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>

      <ConfirmDialog
        open={!!revokeTarget}
        title="Revoke API key?"
        message={`"${revokeTarget?.name}" will be permanently revoked and can no longer be used.`}
        confirmLabel={revoking ? 'Revoking…' : 'Revoke'}
        danger
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </div>
  )
}
