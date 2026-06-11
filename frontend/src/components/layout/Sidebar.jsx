import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  ChevronDown, ChevronRight,
  Cpu, Download, FileCode, Key, LayoutDashboard, Lock,
  LogOut, PlusCircle, Server, ShieldCheck, Terminal,
  User, UsersRound,
} from 'lucide-react'
import { getGatewayUrl, logout, setGatewayUrl } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import sabcLogo from '../../assets/sabc-logo.png'

function SectionHeader({ label, collapsible, open, onToggle }) {
  return (
    <div
      className={[
        'flex items-center justify-between px-4 pt-4 pb-1',
        collapsible ? 'cursor-pointer select-none' : '',
      ].join(' ')}
      onClick={collapsible ? onToggle : undefined}
    >
      <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
        {label}
      </span>
      {collapsible && (
        open
          ? <ChevronDown size={11} className="text-gray-500" />
          : <ChevronRight size={11} className="text-gray-500" />
      )}
    </div>
  )
}

function NavItem({ path, label, icon: Icon, indent = false }) {
  return (
    <NavLink
      to={path}
      className={({ isActive }) =>
        [
          'flex items-center gap-2.5 py-[8px] text-[12px] font-medium transition-all',
          indent ? 'pl-10 pr-4' : 'px-4',
          isActive
            ? 'border-l-[3px] border-brand bg-brand/15 text-white'
            : 'border-l-[3px] border-transparent text-gray-400 hover:bg-white/5 hover:text-gray-200',
        ].join(' ')
      }
    >
      <Icon size={13} />
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  const t = useT()
  const [editingUrl, setEditingUrl] = useState(false)
  const [urlInput, setUrlInput] = useState(getGatewayUrl())
  const navigate = useNavigate()

  const [reportingOpen, setReportingOpen] = useState(true)
  const [manageOpen, setManageOpen] = useState(true)
  const [nodesOpen, setNodesOpen] = useState(true)
  const [adminOpen, setAdminOpen] = useState(true)

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
        <img
          src={sabcLogo}
          alt="SABC"
          className="h-9 w-9 rounded-full border border-gray-400/40 object-cover"
        />
        <div className="text-[10px] text-gray-500 mt-1.5 pl-0.5">{t('nav.platform')}</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">

        {/* COMPLIANCE OVERVIEW — solo, not collapsible */}
        <SectionHeader label={t('nav.sectionOverview')} collapsible={false} />
        <NavItem path="/overview" label={t('nav.overview')} icon={LayoutDashboard} />

        {/* REPORTING */}
        <SectionHeader
          label={t('nav.sectionReporting')}
          collapsible
          open={reportingOpen}
          onToggle={() => setReportingOpen((v) => !v)}
        />
        {reportingOpen && (
          <>
            <NavItem path="/compliance" label={t('nav.scanReports')}  icon={ShieldCheck} />
            <NavItem path="/audit"      label={t('nav.exportedData')} icon={Download}    />
          </>
        )}

        {/* MANAGE COMPLIANCE */}
        <SectionHeader
          label={t('nav.sectionManage')}
          collapsible
          open={manageOpen}
          onToggle={() => setManageOpen((v) => !v)}
        />
        {manageOpen && (
          <>
            <NavItem path="/infrastructure" label={t('nav.inventory')}       icon={Cpu}      />
            <NavItem path="/jobs"           label={t('nav.activityFeed')}    icon={Terminal} />
            <NavItem path="/rules"          label={t('nav.customProfiles')}  icon={FileCode} />
          </>
        )}

        {/* NODES */}
        <SectionHeader
          label={t('nav.sectionNodes')}
          collapsible
          open={nodesOpen}
          onToggle={() => setNodesOpen((v) => !v)}
        />
        {nodesOpen && (
          <>
            <NavItem path="/nodes"   label={t('nav.nodes')}  icon={Server}     />
            <NavItem path="/add-vm"  label={t('nav.addVm')}  icon={PlusCircle} />
          </>
        )}

        {/* ADMINISTRATION */}
        <SectionHeader
          label={t('nav.sectionAdmin')}
          collapsible
          open={adminOpen}
          onToggle={() => setAdminOpen((v) => !v)}
        />
        {adminOpen && (
          <>
            <NavItem path="/iam/users"       label={t('nav.iamUsers')}       icon={User}       />
            <NavItem path="/iam/groups"      label={t('nav.iamGroups')}      icon={UsersRound} />
            <NavItem path="/iam/keys"        label={t('nav.iamKeys')}        icon={Key}        />
            <NavItem path="/iam/permissions" label={t('nav.iamPermissions')} icon={Lock}       />
          </>
        )}
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
