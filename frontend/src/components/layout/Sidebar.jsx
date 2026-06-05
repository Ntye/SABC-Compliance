import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  BarChart2, Cpu, FileCode, Key, List, LogOut,
  PlusCircle, Server, ShieldCheck, Terminal,
} from 'lucide-react'
import { getGatewayUrl, logout, setGatewayUrl } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import sabcLogo from '../../assets/sabc-logo.svg'

export default function Sidebar() {
  const t = useT()
  const [editingUrl, setEditingUrl] = useState(false)
  const [urlInput,   setUrlInput]   = useState(getGatewayUrl())
  const navigate = useNavigate()

  const NAV_ITEMS = [
    { path: '/overview',       label: t('nav.overview'),        icon: BarChart2   },
    { path: '/nodes',          label: t('nav.nodes'),           icon: Server      },
    { path: '/add-vm',         label: t('nav.addVm'),           icon: PlusCircle  },
    { path: '/infrastructure', label: t('nav.infrastructure'),  icon: Cpu         },
    { path: '/jobs',           label: t('nav.jobs'),            icon: Terminal    },
    { path: '/compliance',     label: t('nav.compliance'),      icon: ShieldCheck },
    { path: '/rules',          label: t('nav.rules'),           icon: FileCode    },
    { path: '/keys',           label: t('nav.keys'),            icon: Key         },
    { path: '/audit',          label: t('nav.audit'),           icon: List        },
  ]

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
      <div className="px-4 pt-4 pb-3 border-b border-white/5">
        <img src={sabcLogo} alt="SABC" className="h-9 w-9 rounded-full border border-gray-400/40 object-cover" />
        <div className="text-[10px] text-gray-500 mt-1.5 pl-0.5">{t('nav.platform')}</div>
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
        <a
          href={`${getGatewayUrl()}/docs`}
          target="_blank"
          rel="noreferrer"
          className="block text-[10px] text-gray-600 hover:text-brand transition-colors"
        >
          {t('nav.apiDocs')}
        </a>
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-[11px] text-gray-600 hover:text-red-400 transition-colors"
        >
          <LogOut size={12} />
          {t('nav.signOut')}
        </button>
      </div>
    </aside>
  )
}
