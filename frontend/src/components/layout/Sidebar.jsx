import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  BarChart2,
  Cpu,
  FileCode,
  Key,
  List,
  LogOut,
  PlusCircle,
  Server,
  ShieldCheck,
  Terminal,
} from 'lucide-react'
import { getGatewayUrl, logout, setGatewayUrl } from '../../lib/api.js'
import { useNavigate } from 'react-router-dom'

const NAV_ITEMS = [
  { path: '/overview', label: 'Overview', icon: BarChart2 },
  { path: '/nodes', label: 'Node Registry', icon: Server },
  { path: '/add-vm', label: 'Add VM', icon: PlusCircle },
  { path: '/infrastructure', label: 'Infrastructure', icon: Cpu },
  { path: '/jobs', label: 'Jobs', icon: Terminal },
  { path: '/compliance', label: 'Compliance', icon: ShieldCheck },
  { path: '/rules', label: 'Puppet Rules', icon: FileCode },
  { path: '/keys', label: 'API Keys', icon: Key },
  { path: '/audit', label: 'Audit Log', icon: List },
]

export default function Sidebar() {
  const [editingUrl, setEditingUrl] = useState(false)
  const [urlInput, setUrlInput] = useState(getGatewayUrl())
  const navigate = useNavigate()

  function handleUrlSave() {
    setGatewayUrl(urlInput.trim() || getGatewayUrl())
    setEditingUrl(false)
  }

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="w-[220px] flex-shrink-0 bg-sidebar-bg flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 pt-5 pb-4 border-b border-white/5">
        <div className="text-[14px] font-semibold text-brand leading-none">BdC</div>
        <div className="text-[11px] text-gray-500 mt-0.5">Compliance Platform</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-4 py-[9px] text-[13px] font-medium transition-all',
                isActive
                  ? 'border-l-[3px] border-brand bg-brand/15 text-white'
                  : 'border-l-[3px] border-transparent text-gray-400 hover:bg-white/5 hover:text-gray-200',
              ].join(' ')
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-white/5 space-y-2">
        {/* Gateway URL */}
        <div className="text-[10px] text-gray-600 font-mono truncate">
          {editingUrl ? (
            <input
              autoFocus
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onBlur={handleUrlSave}
              onKeyDown={(e) => { if (e.key === 'Enter') handleUrlSave() }}
              className="w-full bg-white/10 text-gray-300 text-[10px] font-mono px-1 rounded outline-none border border-white/20"
            />
          ) : (
            <button
              onClick={() => setEditingUrl(true)}
              className="font-mono text-[10px] text-gray-600 hover:text-gray-400 truncate text-left w-full"
              title="Click to edit gateway URL"
            >
              {getGatewayUrl()}
            </button>
          )}
        </div>
        {/* Swagger link */}
        <a
          href={`${getGatewayUrl()}/docs`}
          target="_blank"
          rel="noreferrer"
          className="block text-[10px] text-gray-600 hover:text-brand transition-colors"
        >
          API Docs ↗
        </a>
        {/* Logout */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-[11px] text-gray-600 hover:text-red-400 transition-colors"
        >
          <LogOut size={12} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
