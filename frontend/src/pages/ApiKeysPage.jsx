import { useState } from 'react'
import { Key, Plus, Trash2 } from 'lucide-react'
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import Spinner from '../components/common/Spinner.jsx'

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

export default function ApiKeysPage() {
  const t = useT()
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
      toast(t('keys.created'), 'success')
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
      toast(t('keys.revoked'), 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRevoking(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-6">{t('keys.title')}</h2>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-6 max-w-lg">
        <h3 className="text-[13px] font-semibold text-gray-700 mb-4">{t('keys.createTitle')}</h3>
        <form onSubmit={handleCreate} className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('keys.name')}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('keys.namePlaceholder')}
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('keys.role')}</label>
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
            {creating ? t('keys.creating') : t('keys.createBtn')}
          </button>
        </form>

        {/* New key created — key value is not shown for security */}
        {newKey && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-[11px] font-medium text-green-800">
              {t('keys.createSuccess', { name: newKey.name })}
            </p>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading && (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />)}
          </div>
        )}
        {error && (
          <div className="p-4 border border-red-200 bg-red-50 rounded-lg m-4">
            <p className="text-[12px] text-red-600">{error}</p>
          </div>
        )}
        {!loading && !error && keys && (
          keys.length === 0 ? (
            <EmptyState icon={Key} title={t('keys.noKeys')} description={t('keys.noKeysDesc')} />
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{t('keys.colName')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{t('keys.colRole')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{t('keys.colStatus')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{t('keys.colLastUsed')}</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{t('keys.colCreated')}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium">{k.name}</td>
                    <td className="px-4 py-3"><span className={badge(k.role)}>{k.role}</span></td>
                    <td className="px-4 py-3">
                      <span className={badge(k.active ? 'success' : 'gray')}>
                        {k.active ? t('common.active') : t('common.revoked')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-[12px]">{relativeTime(k.last_used, t)}</td>
                    <td className="px-4 py-3 text-gray-400 text-[12px]">{relativeTime(k.created_at, t)}</td>
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
        title={t('keys.revokeTitle')}
        message={t('keys.revokeMsg', { name: revokeTarget?.name ?? '' })}
        confirmLabel={revoking ? t('keys.revoking') : t('keys.revoke')}
        danger
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </div>
  )
}
