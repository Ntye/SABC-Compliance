import { useState } from 'react'
import { Plus, Pencil, Trash2, UserPlus, X, Users } from 'lucide-react'
import {
  listUserGroups, createUserGroup, updateUserGroup, deleteUserGroup,
  addGroupMember, removeGroupMember, listUsers,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

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

function GroupForm({ initial, onSave, onCancel, saving, t }) {
  const [name, setName] = useState(initial?.name || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [role, setRole] = useState(initial?.role || 'readonly')

  function handleSubmit(e) {
    e.preventDefault()
    onSave({ name: name.trim(), description: description.trim() || undefined, role })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.groupName')} *</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
          className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
      </div>
      <div>
        <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.description')}</label>
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
      </div>
      <div>
        <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('iam.role')}</label>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
        >
          <option value="readonly">{t('iam.readonly')}</option>
          <option value="operator">{t('iam.operator')}</option>
          <option value="admin">{t('iam.admin')}</option>
        </select>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
        >
          {saving ? <Spinner size={12} /> : <Plus size={12} />}
          {saving ? 'Saving…' : t('common.save')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50"
        >
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}

function MembersPanel({ group, users, onAddMember, onRemoveMember, onClose, saving, t }) {
  const [selectedUserId, setSelectedUserId] = useState('')
  const usersById = Object.fromEntries((users || []).map((u) => [u.id, u]))
  const memberUsers = (group.member_ids || []).map((id) => usersById[id]).filter(Boolean)
  const nonMembers = (users || []).filter((u) => !group.member_ids?.includes(u.id) && u.active)

  return (
    <Modal title={`${t('iam.manageMembers')} — ${group.name}`} onClose={onClose}>
      <div className="space-y-4">
        {/* Current members */}
        <div>
          <p className="text-[11px] font-medium text-gray-500 mb-2">{t('iam.members')} ({memberUsers.length})</p>
          {memberUsers.length === 0 ? (
            <p className="text-[12px] text-gray-400 italic">No members yet</p>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {memberUsers.map((u) => (
                <div key={u.id} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-medium text-gray-800">{u.username}</span>
                    <span className={badge(u.role)}>{u.role}</span>
                  </div>
                  <button
                    onClick={() => onRemoveMember(group.id, u.id)}
                    disabled={saving}
                    className="text-[11px] text-red-500 hover:text-red-700 hover:bg-red-50 px-2 py-0.5 rounded transition-colors disabled:opacity-50"
                  >
                    {t('iam.removeMember')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add member */}
        {nonMembers.length > 0 && (
          <div>
            <p className="text-[11px] font-medium text-gray-500 mb-2">{t('iam.addMember')}</p>
            <div className="flex gap-2">
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="flex-1 px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
              >
                <option value="">{t('iam.selectUser')}</option>
                {nonMembers.map((u) => (
                  <option key={u.id} value={u.id}>{u.username} ({u.role})</option>
                ))}
              </select>
              <button
                onClick={() => {
                  if (selectedUserId) {
                    onAddMember(group.id, selectedUserId)
                    setSelectedUserId('')
                  }
                }}
                disabled={!selectedUserId || saving}
                className="inline-flex items-center gap-1 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
              >
                {saving ? <Spinner size={12} /> : <UserPlus size={12} />}
                {t('iam.addMember')}
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function UserGroupsPage() {
  const t = useT()
  const toast = useToast()
  const { data: groups, loading, error, refetch } = useApi(listUserGroups)
  const { data: users } = useApi(listUsers)

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [membersTarget, setMembersTarget] = useState(null)
  const [saving, setSaving] = useState(false)

  async function handleCreate(data) {
    setSaving(true)
    try {
      await createUserGroup(data)
      toast(t('iam.groupsTitle') + ' created', 'success')
      setShowCreate(false)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdate(data) {
    setSaving(true)
    try {
      await updateUserGroup(editTarget.id, data)
      toast('Group updated', 'success')
      setEditTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(group) {
    if (!window.confirm(t('iam.deleteGroupConfirm', { name: group.name }))) return
    setSaving(true)
    try {
      await deleteUserGroup(group.id)
      toast('Group deleted', 'success')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleAddMember(groupId, userId) {
    setSaving(true)
    try {
      await addGroupMember(groupId, userId)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleRemoveMember(groupId, userId) {
    setSaving(true)
    try {
      await removeGroupMember(groupId, userId)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const activeMembersTarget = membersTarget
    ? (groups || []).find((g) => g.id === membersTarget.id) || membersTarget
    : null

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('iam.groupsTitle')}</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors"
        >
          <Plus size={13} />
          {t('iam.createGroup')}
        </button>
      </div>

      {/* Groups */}
      {loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 bg-gray-100 animate-pulse rounded-xl" />
          ))}
        </div>
      )}
      {error && (
        <div className="p-4 border border-red-200 bg-red-50 rounded-lg">
          <p className="text-[12px] text-red-600">{error}</p>
        </div>
      )}
      {!loading && !error && groups && (
        groups.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-[13px] text-gray-400">
            {t('iam.noGroups')}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {groups.map((g) => (
              <div key={g.id} className="bg-white rounded-xl border border-gray-100 p-4 hover:border-gray-200 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center">
                      <Users size={14} className="text-brand" />
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-gray-800">{g.name}</p>
                      <span className={badge(g.role)}>{g.role}</span>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditTarget(g)}
                      className="p-1.5 text-gray-400 hover:text-brand rounded hover:bg-brand/5 transition-colors"
                    >
                      <Pencil size={12} />
                    </button>
                    <button
                      onClick={() => handleDelete(g)}
                      className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 transition-colors"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                {g.description && (
                  <p className="text-[11px] text-gray-400 mb-3 line-clamp-2">{g.description}</p>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-gray-50">
                  <span className="text-[11px] text-gray-400">
                    {g.member_ids?.length ?? 0} {g.member_ids?.length === 1 ? 'member' : 'members'}
                  </span>
                  <button
                    onClick={() => setMembersTarget(g)}
                    className="inline-flex items-center gap-1 text-[11px] text-brand hover:text-brand/80 font-medium transition-colors"
                  >
                    <UserPlus size={11} />
                    {t('iam.manageMembers')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Create modal */}
      {showCreate && (
        <Modal title={t('iam.createGroup')} onClose={() => setShowCreate(false)}>
          <GroupForm onSave={handleCreate} onCancel={() => setShowCreate(false)} saving={saving} t={t} />
        </Modal>
      )}

      {/* Edit modal */}
      {editTarget && (
        <Modal title={`Edit — ${editTarget.name}`} onClose={() => setEditTarget(null)}>
          <GroupForm
            initial={editTarget}
            onSave={handleUpdate}
            onCancel={() => setEditTarget(null)}
            saving={saving}
            t={t}
          />
        </Modal>
      )}

      {/* Members panel */}
      {activeMembersTarget && (
        <MembersPanel
          group={activeMembersTarget}
          users={users}
          onAddMember={handleAddMember}
          onRemoveMember={handleRemoveMember}
          onClose={() => setMembersTarget(null)}
          saving={saving}
          t={t}
        />
      )}
    </div>
  )
}
