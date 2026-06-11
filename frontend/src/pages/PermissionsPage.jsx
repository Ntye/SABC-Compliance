import { CheckCircle, XCircle } from 'lucide-react'
import { listUsers, updateUser } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import { useState } from 'react'

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
  const toast = useToast()
  const { data: users, loading, refetch } = useApi(listUsers)
  const [saving, setSaving] = useState(null)

  async function handleRoleChange(user, newRole) {
    setSaving(user.id)
    try {
      await updateUser(user.id, { role: newRole })
      toast('Role updated', 'success')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(null)
    }
  }

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
        <div className="px-5 py-3 border-b border-gray-100">
          <h3 className="text-[13px] font-semibold text-gray-800">{t('iam.roleAssignments')}</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">Change a user's role directly here.</p>
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
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.username')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.email')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.status')}</th>
                  <th className="text-left px-5 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{t('iam.role')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-3 font-medium text-gray-800">{u.username}</td>
                    <td className="px-5 py-3 text-gray-400">{u.email || '—'}</td>
                    <td className="px-5 py-3">
                      <span className={badge(u.active ? 'success' : 'gray')}>
                        {u.active ? t('iam.active') : t('iam.inactive')}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        {saving === u.id ? (
                          <Spinner size={12} />
                        ) : (
                          <select
                            value={u.role}
                            onChange={(e) => handleRoleChange(u, e.target.value)}
                            disabled={!u.active}
                            className="px-2 py-1 text-[11px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <option value="readonly">{t('iam.readonly')}</option>
                            <option value="operator">{t('iam.operator')}</option>
                            <option value="admin">{t('iam.admin')}</option>
                          </select>
                        )}
                      </div>
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
