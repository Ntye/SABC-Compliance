import { useState } from 'react'
import { Plus, Pencil, UserX, UserCheck, X } from 'lucide-react'
import { listUsers, createUser, updateUser, deleteUser } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
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

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl border border-gray-100 shadow-xl w-full max-w-md mx-4 p-6">
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

export default function UsersPage() {
  const t = useT()
  const toast = useToast()
  const { data: users, loading, error, refetch } = useApi(listUsers)

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [saving, setSaving] = useState(false)

  // Create form state
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newConfirm, setNewConfirm] = useState('')
  const [newRole, setNewRole] = useState('readonly')
  const [newEmail, setNewEmail] = useState('')

  // Edit form state
  const [editRole, setEditRole] = useState('readonly')
  const [editEmail, setEditEmail] = useState('')

  function openCreate() {
    setNewUsername(''); setNewPassword(''); setNewConfirm('')
    setNewRole('readonly'); setNewEmail('')
    setShowCreate(true)
  }

  function openEdit(user) {
    setEditRole(user.role)
    setEditEmail(user.email || '')
    setEditTarget(user)
  }

  async function handleCreate(e) {
    e.preventDefault()
    if (!newUsername.trim() || !newPassword) {
      toast(t('iam.username') + ' / ' + t('iam.password') + ' required', 'error')
      return
    }
    if (newPassword !== newConfirm) {
      toast('Passwords do not match', 'error')
      return
    }
    setSaving(true)
    try {
      await createUser({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
        email: newEmail.trim() || undefined,
      })
      toast(t('iam.usersTitle') + ' created', 'success')
      setShowCreate(false)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleEdit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await updateUser(editTarget.id, {
        role: editRole,
        email: editEmail.trim() || null,
      })
      toast('User updated', 'success')
      setEditTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleActive(user) {
    setSaving(true)
    try {
      await updateUser(user.id, { active: !user.active })
      toast(user.active ? 'User deactivated' : 'User activated', 'success')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('iam.usersTitle')}</h2>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors"
        >
          <Plus size={13} />
          {t('iam.createUser')}
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading && (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />
            ))}
          </div>
        )}
        {error && (
          <div className="p-4 border border-red-200 bg-red-50 rounded-lg m-4">
            <p className="text-[12px] text-red-600">{error}</p>
          </div>
        )}
        {!loading && !error && users && (
          users.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-gray-400">{t('iam.noUsers')}</div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.username')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.role')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.email')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.status')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Created</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.lastLogin')}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium text-gray-800">{u.username}</td>
                    <td className="px-4 py-3">
                      <span className={badge(u.role)}>{u.role}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{u.email || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={badge(u.active ? 'success' : 'gray')}>
                        {u.active ? t('iam.active') : t('iam.inactive')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{relativeTime(u.created_at, t)}</td>
                    <td className="px-4 py-3 text-gray-400">{relativeTime(u.last_login, t)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => openEdit(u)}
                          title={t('iam.editRole')}
                          className="p-1.5 text-gray-400 hover:text-brand rounded hover:bg-brand/5 transition-colors"
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          onClick={() => handleToggleActive(u)}
                          title={u.active ? t('iam.deactivate') : t('iam.activate')}
                          className={[
                            'p-1.5 rounded transition-colors',
                            u.active
                              ? 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                              : 'text-gray-400 hover:text-green-600 hover:bg-green-50',
                          ].join(' ')}
                        >
                          {u.active ? <UserX size={12} /> : <UserCheck size={12} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>

      {/* Create User Modal */}
      {showCreate && (
        <Modal title={t('iam.createUser')} onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.username')} *</label>
              <input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                autoFocus
                required
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.email')}</label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.role')}</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
              >
                <option value="readonly">{t('iam.readonly')}</option>
                <option value="operator">{t('iam.operator')}</option>
                <option value="admin">{t('iam.admin')}</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.password')} *</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.confirmPassword')} *</label>
              <input
                type="password"
                value={newConfirm}
                onChange={(e) => setNewConfirm(e.target.value)}
                required
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
              >
                {saving ? <Spinner size={12} /> : <Plus size={12} />}
                {saving ? 'Creating…' : t('iam.createUser')}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50"
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Edit User Modal */}
      {editTarget && (
        <Modal title={`${t('iam.editRole')} — ${editTarget.username}`} onClose={() => setEditTarget(null)}>
          <form onSubmit={handleEdit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.role')}</label>
              <select
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
              >
                <option value="readonly">{t('iam.readonly')}</option>
                <option value="operator">{t('iam.operator')}</option>
                <option value="admin">{t('iam.admin')}</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.email')}</label>
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
              >
                {saving ? <Spinner size={12} /> : null}
                {saving ? 'Saving…' : t('common.save')}
              </button>
              <button
                type="button"
                onClick={() => setEditTarget(null)}
                className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50"
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
