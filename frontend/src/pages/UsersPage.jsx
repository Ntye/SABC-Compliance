import { useState, useMemo } from 'react'
import { Plus, Pencil, UserX, UserCheck, X, Search } from 'lucide-react'
import { listUsers, createUser, updateUser, deleteUser, listUserGroups, addGroupMember, removeGroupMember } from '../lib/api.js'
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
  const { data: groups } = useApi(listUserGroups)

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [saving, setSaving] = useState(false)

  // Filter state
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Create form state
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newConfirm, setNewConfirm] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newGroupId, setNewGroupId] = useState('')

  // Edit form state
  const [editEmail, setEditEmail] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editConfirm, setEditConfirm] = useState('')
  const [editGroupId, setEditGroupId] = useState('')
  const [editActive, setEditActive] = useState(true)

  // Map each user id → the names of the groups they belong to
  const groupNamesByUser = useMemo(() => {
    const map = {}
    for (const g of groups || []) {
      for (const uid of g.member_ids || []) {
        (map[uid] ||= []).push(g.name)
      }
    }
    return map
  }, [groups])

  const filtered = useMemo(() => {
    if (!users) return []
    const q = query.toLowerCase()
    return users.filter((u) => {
      if (statusFilter === 'active' && !u.active) return false
      if (statusFilter === 'inactive' && u.active) return false
      if (q && !u.username.toLowerCase().includes(q) && !(u.email || '').toLowerCase().includes(q)) return false
      return true
    })
  }, [users, query, statusFilter])

  function openCreate() {
    setNewUsername(''); setNewPassword(''); setNewConfirm('')
    setNewEmail(''); setNewGroupId('')
    setShowCreate(true)
  }

  function openEdit(user) {
    setEditEmail(user.email || '')
    setEditPassword('')
    setEditConfirm('')
    setEditActive(user.active !== false)
    // pre-select the first group the user currently belongs to
    const currentGroupId = (groups || []).find((g) => (g.member_ids || []).includes(user.id))?.id || ''
    setEditGroupId(currentGroupId)
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
    if (!newGroupId) {
      toast(t('iam.userGroup') + ' required', 'error')
      return
    }
    setSaving(true)
    try {
      const created = await createUser({
        username: newUsername.trim(),
        password: newPassword,
        email: newEmail.trim() || undefined,
      })
      try {
        await addGroupMember(newGroupId, created.id)
      } catch {
        // non-fatal — user was created, but warn that group assignment failed
        toast('User created but group assignment failed', 'warning')
      }
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
    if (editPassword && editPassword !== editConfirm) {
      toast('Passwords do not match', 'error')
      return
    }
    if (!editGroupId) {
      toast(t('iam.userGroup') + ' required', 'error')
      return
    }
    setSaving(true)
    try {
      const patch = { email: editEmail.trim() || null, active: editActive }
      if (editPassword) patch.password = editPassword
      await updateUser(editTarget.id, patch)

      // Reassign group only if it changed
      const prevGroupId = (groups || []).find((g) => (g.member_ids || []).includes(editTarget.id))?.id
      if (editGroupId !== prevGroupId) {
        if (prevGroupId) {
          try { await removeGroupMember(prevGroupId, editTarget.id) } catch { /* ignore */ }
        }
        await addGroupMember(editGroupId, editTarget.id)
      }

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
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('iam.usersTitle')}</h2>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors"
        >
          <Plus size={13} />
          {t('iam.createUser')}
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg flex-1 min-w-[160px] max-w-[280px]">
          <Search size={13} className="text-gray-400 flex-shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search users…"
            className="flex-1 text-[12px] outline-none bg-transparent text-gray-700 placeholder-gray-400"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-[12px] bg-white border border-gray-200 rounded-lg outline-none focus:border-brand text-gray-700"
        >
          <option value="all">All statuses</option>
          <option value="active">{t('iam.active')}</option>
          <option value="inactive">{t('iam.inactive')}</option>
        </select>
        {(query || statusFilter !== 'all') && (
          <button
            onClick={() => { setQuery(''); setStatusFilter('all') }}
            className="text-[11px] text-gray-400 hover:text-gray-600 px-2 py-1.5"
          >
            Clear
          </button>
        )}
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
          filtered.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-gray-400">
              {users.length === 0 ? t('iam.noUsers') : 'No users match the filters.'}
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.username')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.userGroup')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.email')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.status')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Created</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('iam.lastLogin')}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium text-gray-800">{u.username}</td>
                    <td className="px-4 py-3">
                      {(groupNamesByUser[u.id] || []).length === 0 ? (
                        <span className={badge('gray')}>—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {groupNamesByUser[u.id].map((name) => (
                            <span key={name} className={badge(name)}>{name}</span>
                          ))}
                        </div>
                      )}
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
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.userGroup')} *</label>
              <select
                value={newGroupId}
                onChange={(e) => setNewGroupId(e.target.value)}
                required
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
              >
                <option value="" disabled>{t('iam.selectGroup')}</option>
                {(groups || []).map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
              <p className="text-[10px] text-gray-400 mt-1">{t('iam.groupRequiredHint')}</p>
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
        <Modal title={`Edit — ${editTarget.username}`} onClose={() => setEditTarget(null)}>
          <form onSubmit={handleEdit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.email')}</label>
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                placeholder="user@example.com"
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            {/* User group */}
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.userGroup')} *</label>
              <select
                value={editGroupId}
                onChange={(e) => setEditGroupId(e.target.value)}
                required
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
              >
                <option value="" disabled>{t('iam.selectGroup')}</option>
                {(groups || []).map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            {/* New password (optional) */}
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">
                {t('iam.password')} <span className="font-normal text-gray-400">(leave blank to keep current)</span>
              </label>
              <input
                type="password"
                value={editPassword}
                onChange={(e) => setEditPassword(e.target.value)}
                autoComplete="new-password"
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            {editPassword && (
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.confirmPassword')} *</label>
                <input
                  type="password"
                  value={editConfirm}
                  onChange={(e) => setEditConfirm(e.target.value)}
                  required
                  className={`w-full px-3 py-2 text-[12px] border rounded-lg outline-none focus:ring-2 focus:ring-brand/15 ${
                    editConfirm && editConfirm !== editPassword ? 'border-red-400 focus:border-red-400' : 'border-gray-200 focus:border-brand'
                  }`}
                />
                {editConfirm && editConfirm !== editPassword && (
                  <p className="text-[10px] text-red-500 mt-1">Passwords do not match</p>
                )}
              </div>
            )}
            {/* Active toggle */}
            <div className="flex items-center gap-2">
              <input
                id="edit-active"
                type="checkbox"
                checked={editActive}
                onChange={(e) => setEditActive(e.target.checked)}
                className="w-3.5 h-3.5 accent-brand"
              />
              <label htmlFor="edit-active" className="text-[12px] text-gray-700 select-none cursor-pointer">
                {t('iam.active')}
              </label>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={saving || (editPassword !== '' && editPassword !== editConfirm)}
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
