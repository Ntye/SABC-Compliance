import { useState, useMemo } from 'react'
import { Plus, Pencil, Trash2, UserPlus, X, Users, Lock, Search } from 'lucide-react'
import {
  listUserGroups, createUserGroup, updateUserGroup, deleteUserGroup,
  addGroupMember, removeGroupMember, listUsers,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

// All available permissions (must match backend UserGroup.ALL_PERMISSIONS)
const ALL_PERMISSIONS = [
  { id: 'view_nodes',          label: 'View nodes & jobs',          group: 'Nodes'       },
  { id: 'ping_nodes',          label: 'Ping nodes',                 group: 'Nodes'       },
  { id: 'register_nodes',      label: 'Register nodes',             group: 'Nodes'       },
  { id: 'delete_nodes',        label: 'Delete nodes',               group: 'Nodes'       },
  { id: 'run_playbooks',       label: 'Run Ansible playbooks',      group: 'Automation'  },
  { id: 'install_agents',      label: 'Install Puppet/Wazuh agents',group: 'Automation'  },
  { id: 'view_compliance',     label: 'View compliance reports',    group: 'Compliance'  },
  { id: 'collect_compliance',  label: 'Collect compliance data',    group: 'Compliance'  },
  { id: 'trigger_remediation', label: 'Trigger remediation',        group: 'Compliance'  },
  { id: 'cancel_jobs',         label: 'Cancel jobs',                group: 'Jobs'        },
  { id: 'view_audit',          label: 'View audit log',             group: 'Admin'       },
  { id: 'manage_api_keys',     label: 'Manage API keys',            group: 'Admin'       },
  { id: 'manage_users',        label: 'Manage users',               group: 'Admin'       },
  { id: 'manage_groups',       label: 'Manage user groups',         group: 'Admin'       },
  { id: 'change_password',     label: 'Change own password',        group: 'Account'     },
]
const PERM_GROUPS = [...new Set(ALL_PERMISSIONS.map((p) => p.group))]

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

function PermissionsEditor({ selected, onChange, disabled }) {
  function toggle(id) {
    if (disabled) return
    onChange(
      selected.includes(id)
        ? selected.filter((p) => p !== id)
        : [...selected, id]
    )
  }

  function toggleGroup(grp) {
    if (disabled) return
    const ids = ALL_PERMISSIONS.filter((p) => p.group === grp).map((p) => p.id)
    const allOn = ids.every((id) => selected.includes(id))
    const next = allOn
      ? selected.filter((id) => !ids.includes(id))
      : [...new Set([...selected, ...ids])]
    onChange(next)
  }

  return (
    <div className="space-y-3">
      {PERM_GROUPS.map((grp) => {
        const perms = ALL_PERMISSIONS.filter((p) => p.group === grp)
        const allOn = perms.every((p) => selected.includes(p.id))
        return (
          <div key={grp}>
            <label
              className={[
                'flex items-center gap-2 text-[11px] font-semibold text-gray-600 mb-1.5',
                disabled ? 'cursor-default' : 'cursor-pointer',
              ].join(' ')}
              onClick={() => toggleGroup(grp)}
            >
              <input
                type="checkbox"
                readOnly
                checked={allOn}
                disabled={disabled}
                className="accent-brand"
              />
              {grp}
            </label>
            <div className="grid grid-cols-2 gap-1 pl-4">
              {perms.map((p) => (
                <label
                  key={p.id}
                  className={[
                    'flex items-center gap-1.5 text-[11px] text-gray-500',
                    disabled ? 'cursor-default opacity-70' : 'cursor-pointer hover:text-gray-700',
                  ].join(' ')}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(p.id)}
                    onChange={() => toggle(p.id)}
                    disabled={disabled}
                    className="accent-brand"
                  />
                  {p.label}
                </label>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function GroupForm({ initial, onSave, onCancel, saving, t }) {
  const [name, setName] = useState(initial?.name || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [role, setRole] = useState(initial?.role || 'readonly')
  const [permissions, setPermissions] = useState(initial?.permissions || [])

  function handleSubmit(e) {
    e.preventDefault()
    onSave({ name: name.trim(), description: description.trim() || undefined, role, permissions })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
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
        <label className="block text-[11px] font-medium text-gray-500 mb-2">Permissions</label>
        <div className="border border-gray-100 rounded-lg p-3 bg-gray-50/50 max-h-64 overflow-y-auto">
          <PermissionsEditor selected={permissions} onChange={setPermissions} disabled={false} />
        </div>
        <p className="text-[10px] text-gray-400 mt-1">{permissions.length} permission{permissions.length !== 1 ? 's' : ''} selected</p>
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
        <button type="button" onClick={onCancel}
          className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50">
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
        <div>
          <p className="text-[11px] font-medium text-gray-500 mb-2">{t('iam.members')} ({memberUsers.length})</p>
          {memberUsers.length === 0 ? (
            <p className="text-[12px] text-gray-400 italic">No members yet</p>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {memberUsers.map((u) => (
                <div key={u.id} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-medium text-gray-800">{u.username}</span>
                    <span className={badge(u.role)}>{u.role}</span>
                  </div>
                  <button onClick={() => onRemoveMember(group.id, u.id)} disabled={saving}
                    className="text-[11px] text-red-500 hover:text-red-700 px-2 py-0.5 rounded hover:bg-red-50 transition-colors disabled:opacity-50">
                    {t('iam.removeMember')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        {nonMembers.length > 0 && (
          <div>
            <p className="text-[11px] font-medium text-gray-500 mb-2">{t('iam.addMember')}</p>
            <div className="flex gap-2">
              <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)}
                className="flex-1 px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white">
                <option value="">{t('iam.selectUser')}</option>
                {nonMembers.map((u) => (
                  <option key={u.id} value={u.id}>{u.username} ({u.role})</option>
                ))}
              </select>
              <button
                onClick={() => { if (selectedUserId) { onAddMember(group.id, selectedUserId); setSelectedUserId('') } }}
                disabled={!selectedUserId || saving}
                className="inline-flex items-center gap-1 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
              >
                {saving ? <Spinner size={12} /> : <UserPlus size={12} />}
                Add
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
  const [filter, setFilter] = useState('')

  const filtered = useMemo(() => {
    if (!groups) return []
    const q = filter.trim().toLowerCase()
    if (!q) return groups
    return groups.filter((g) =>
      g.name.toLowerCase().includes(q) ||
      (g.description || '').toLowerCase().includes(q) ||
      g.role.toLowerCase().includes(q)
    )
  }, [groups, filter])

  async function handleCreate(data) {
    setSaving(true)
    try {
      await createUserGroup(data)
      toast('Group created', 'success')
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
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('iam.groupsTitle')}</h2>
        <button onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors">
          <Plus size={13} /> {t('iam.createGroup')}
        </button>
      </div>

      {/* Filter */}
      <div className="relative mb-4 max-w-xs">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter groups…"
          className="w-full pl-8 pr-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 bg-white"
        />
      </div>

      {loading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-32 bg-gray-100 animate-pulse rounded-xl" />)}
        </div>
      )}
      {error && <div className="p-4 border border-red-200 bg-red-50 rounded-lg text-[12px] text-red-600">{error}</div>}

      {!loading && !error && (
        filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-[13px] text-gray-400">
            {filter ? 'No groups match your filter.' : t('iam.noGroups')}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((g) => (
              <div key={g.id} className={[
                'bg-white rounded-xl border p-4 transition-colors',
                g.is_default ? 'border-gray-200 bg-gray-50/50' : 'border-gray-100 hover:border-gray-200',
              ].join(' ')}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={[
                      'w-8 h-8 rounded-lg flex items-center justify-center',
                      g.is_default ? 'bg-gray-100' : 'bg-brand/10',
                    ].join(' ')}>
                      {g.is_default
                        ? <Lock size={13} className="text-gray-400" />
                        : <Users size={13} className="text-brand" />}
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-gray-800">{g.name}</p>
                      <span className={badge(g.role)}>{g.role}</span>
                    </div>
                  </div>
                  {!g.is_default && (
                    <div className="flex gap-1">
                      <button onClick={() => setEditTarget(g)}
                        className="p-1.5 text-gray-400 hover:text-brand rounded hover:bg-brand/5 transition-colors">
                        <Pencil size={12} />
                      </button>
                      <button onClick={() => handleDelete(g)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 transition-colors">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                  {g.is_default && (
                    <span className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider bg-gray-100 px-1.5 py-0.5 rounded">
                      default
                    </span>
                  )}
                </div>
                {g.description && (
                  <p className="text-[11px] text-gray-400 mb-2 line-clamp-2">{g.description}</p>
                )}
                <p className="text-[10px] text-gray-400 mb-3">
                  {g.permissions?.length ?? 0} permission{g.permissions?.length !== 1 ? 's' : ''}
                </p>
                <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                  <span className="text-[11px] text-gray-400">
                    {g.member_ids?.length ?? 0} {g.member_ids?.length === 1 ? 'member' : 'members'}
                  </span>
                  <button onClick={() => setMembersTarget(g)}
                    className="inline-flex items-center gap-1 text-[11px] text-brand hover:text-brand/80 font-medium transition-colors">
                    <UserPlus size={11} /> {t('iam.manageMembers')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {showCreate && (
        <Modal title={t('iam.createGroup')} onClose={() => setShowCreate(false)} wide>
          <GroupForm onSave={handleCreate} onCancel={() => setShowCreate(false)} saving={saving} t={t} />
        </Modal>
      )}
      {editTarget && (
        <Modal title={`Edit — ${editTarget.name}`} onClose={() => setEditTarget(null)} wide>
          <GroupForm initial={editTarget} onSave={handleUpdate} onCancel={() => setEditTarget(null)} saving={saving} t={t} />
        </Modal>
      )}
      {activeMembersTarget && (
        <MembersPanel
          group={activeMembersTarget} users={users}
          onAddMember={handleAddMember} onRemoveMember={handleRemoveMember}
          onClose={() => setMembersTarget(null)} saving={saving} t={t}
        />
      )}
    </div>
  )
}
