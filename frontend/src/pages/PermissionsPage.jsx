import { CheckCircle, XCircle, Search } from 'lucide-react'
import { listUsers, listUserGroups } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import { useState, useMemo } from 'react'

const MATRIX = [
  { action: 'View nodes & jobs',          readonly: true,  operator: true,  admin: true  },
  { action: 'Ping nodes',                  readonly: false, operator: true,  admin: true  },
  { action: 'Register nodes',              readonly: false, operator: true,  admin: true  },
  { action: 'Delete nodes',               readonly: false, operator: false, admin: true  },
  { action: 'Run Ansible playbooks',       readonly: false, operator: true,  admin: true  },
  { action: 'Install Puppet/Wazuh agents', readonly: false, operator: true,  admin: true  },
  { action: 'View compliance reports',     readonly: true,  operator: true,  admin: true  },
  { action: 'Collect compliance data',     readonly: false, operator: true,  admin: true  },
  { action: 'Trigger remediation',         readonly: false, operator: true,  admin: true  },
  { action: 'Cancel jobs',                 readonly: false, operator: true,  admin: true  },
  { action: 'View audit log',              readonly: true,  operator: true,  admin: true  },
  { action: 'Manage API keys',             readonly: false, operator: false, admin: true  },
  { action: 'Manage users',               readonly: false, operator: false, admin: true  },
  { action: 'Manage user groups',         readonly: false, operator: false, admin: true  },
  { action: 'Change own password',         readonly: true,  operator: true,  admin: true  },
]

function Tick({ ok }) {
  return ok
    ? <CheckCircle size={14} className="text-green-500 mx-auto" />
    : <XCircle    size={14} className="text-gray-200 mx-auto" />
}

export default function PermissionsPage() {
  const t = useT()
  const { data: users, loading } = useApi(listUsers)
  const { data: groups } = useApi(listUserGroups)
  const [query, setQuery] = useState('')

  const groupNamesByUser = useMemo(() => {
    const map = {}
    for (const g of groups || []) {
      for (const uid of g.member_ids || []) {
        (map[uid] ||= []).push(g.name)
      }
    }
    return map
  }, [groups])

  const filteredUsers = useMemo(() => {
    if (!users) return []
    const q = query.toLowerCase()
    if (!q) return users
    return users.filter((u) =>
      u.username.toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q)
    )
  }, [users, query])

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <h2 className="text-[18px] font-semibold text-gray-900">{t('iam.permissionsTitle')}</h2>

      {/* Permissions matrix */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h3 className="text-[13px] font-semibold text-gray-800">{t('iam.permissionsMatrix')}</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">Role capabilities are fixed and enforced server-side.</p>
        </div>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider w-1/2">Action</th>
              <th className="text-center px-3 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.readonly')}</th>
              <th className="text-center px-3 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.operator')}</th>
              <th className="text-center px-3 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.admin')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {MATRIX.map((row) => (
              <tr key={row.action} className="hover:bg-gray-50/50">
                <td className="px-5 py-2.5 text-gray-700">{row.action}</td>
                <td className="px-3 py-2.5 text-center"><Tick ok={row.readonly}  /></td>
                <td className="px-3 py-2.5 text-center"><Tick ok={row.operator}  /></td>
                <td className="px-3 py-2.5 text-center"><Tick ok={row.admin}     /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Role assignments */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-4">
          <div>
            <h3 className="text-[13px] font-semibold text-gray-800">{t('iam.roleAssignments')}</h3>
            <p className="text-[11px] text-gray-400 mt-0.5">Roles are assigned via user groups.</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg">
            <Search size={12} className="text-gray-400 flex-shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search users…"
              className="text-[12px] outline-none bg-transparent text-gray-700 placeholder-gray-400 w-36"
            />
          </div>
        </div>
        {loading && (
          <div className="p-6 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />
            ))}
          </div>
        )}
        {!loading && users && (
          users.length === 0 ? (
            <div className="p-6 text-center text-[13px] text-gray-400">{t('iam.noUsers')}</div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-6 text-center text-[13px] text-gray-400">No users match the search.</div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.username')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.email')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.status')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.userGroup')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-3 font-medium text-gray-800">{u.username}</td>
                    <td className="px-5 py-3 text-gray-400">{u.email || '—'}</td>
                    <td className="px-5 py-3">
                      <span className={badge(u.active ? 'success' : 'gray')}>
                        {u.active ? t('iam.active') : t('iam.inactive')}
                      </span>
                    </td>
                    <td className="px-5 py-3">
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
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  )
}
