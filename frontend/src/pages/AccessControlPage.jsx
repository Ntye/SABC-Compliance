import { NavLink, Outlet } from 'react-router-dom'
import { Key, Lock, User, UsersRound } from 'lucide-react'
import { useT } from '../context/LangContext.jsx'

// Access Control consolidates the four IAM views into one tabbed page: Users,
// Groups, API Keys and Permissions. Each tab is a nested route so deep links
// (e.g. /iam/keys) still work and the browser back button behaves.
const TABS = [
  { to: 'users',       labelKey: 'accessControl.tabUsers',       icon: User },
  { to: 'groups',      labelKey: 'accessControl.tabGroups',      icon: UsersRound },
  { to: 'keys',        labelKey: 'accessControl.tabKeys',        icon: Key },
  { to: 'permissions', labelKey: 'accessControl.tabPermissions', icon: Lock },
]

export default function AccessControlPage() {
  const t = useT()
  return (
    <div className="p-6 max-w-6xl">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-1">{t('accessControl.title')}</h2>
      <p className="text-[12px] text-gray-400 mb-5">{t('accessControl.subtitle')}</p>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-gray-200 mb-2">
        {TABS.map(({ to, labelKey, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                'inline-flex items-center gap-1.5 px-3.5 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors',
                isActive
                  ? 'border-brand text-brand'
                  : 'border-transparent text-gray-500 hover:text-gray-800',
              ].join(' ')
            }
          >
            <Icon size={14} />
            {t(labelKey)}
          </NavLink>
        ))}
      </div>

      {/* Active tab content */}
      <Outlet />
    </div>
  )
}
