import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  ChevronDown, ChevronRight,
  Activity, Cpu, Download, FileCode, FileKey, Gauge, Key, LayoutDashboard, Layers,
  LifeBuoy, Lock, LogOut, PlusCircle, Server, ShieldCheck, Sliders, Terminal,
  User, UsersRound,
} from 'lucide-react'
import { logout } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import sabcLogo from '../../assets/bdc-logo.png'

// CRICLO-style plane-based information architecture. Every view is listed for
// every user — visibility is NOT gated by role; individual pages gate the
// *actions* (create/edit/enforce) instead. This gives a single, predictable
// flow: Overview → Fleet → Detection → Enforcement → Validation → Reporting →
// Administration.
function usePlanes(t) {
  return [
    { key: 'overview', label: t('nav.planeOverview'), collapsible: false, items: [
      { path: '/overview', label: t('nav.dashboard'), icon: LayoutDashboard },
    ]},
    { key: 'fleet', label: t('nav.planeFleet'), items: [
      { path: '/nodes',       label: t('nav.nodes'),      icon: Server },
      { path: '/node-groups', label: t('nav.nodeGroups'), icon: Layers },
    ]},
    { key: 'detection', label: t('nav.planeDetection'), items: [
      { path: '/detection', label: t('nav.detectionEvents'), icon: Activity },
    ]},
    { key: 'enforcement', label: t('nav.planeEnforcement'), items: [
      { path: '/profiles', label: t('nav.referentials'),  icon: FileCode },
      { path: '/tiers',    label: t('nav.tiers'),         icon: Gauge },
      { path: '/jobs',     label: t('nav.activityFeed'),  icon: Terminal },
    ]},
    { key: 'validation', label: t('nav.planeValidation'), items: [
      { path: '/compliance', label: t('nav.scanResults'), icon: ShieldCheck },
    ]},
    { key: 'reporting', label: t('nav.planeReporting'), items: [
      { path: '/audit', label: t('nav.reportsEvidence'), icon: Download },
    ]},
    { key: 'admin', label: t('nav.planeAdmin'), items: [
      { path: '/add-server',      label: t('nav.nodeEnrolment'),  icon: PlusCircle },
      { path: '/infrastructure',  label: t('nav.systemHealth'),   icon: Cpu },
      { path: '/iam/users',       label: t('nav.accessControl'),  icon: User },
      { path: '/iam/groups',      label: t('nav.iamGroups'),      icon: UsersRound },
      { path: '/iam/keys',        label: t('nav.iamKeys'),        icon: Key },
      { path: '/iam/permissions', label: t('nav.iamPermissions'), icon: Lock },
      { path: '/settings/tls',    label: t('nav.tlsCertificate'), icon: FileKey },
    ]},
  ]
}

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

function NavItem({ path, label, icon: Icon }) {
  return (
    <NavLink
      to={path}
      end={path === '/overview'}
      className={({ isActive }) =>
        [
          'flex items-center gap-2.5 py-[8px] px-4 text-[12px] font-medium transition-all',
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
  const navigate = useNavigate()
  const planes = usePlanes(t)

  // Collapsible planes default to open; overview/help are always shown.
  const [collapsed, setCollapsed] = useState({})
  const toggle = (k) => setCollapsed((c) => ({ ...c, [k]: !c[k] }))

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="w-[220px] flex-shrink-0 bg-sidebar-bg flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 pt-4">
        <img src={sabcLogo} alt="Boissons du Cameroun" className="w-[110px] object-contain" />
        <div className="text-[10px] text-gray-500 mt-1 uppercase tracking-wider">{t('nav.platform')}</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {planes.map((plane) => {
          const collapsible = plane.collapsible !== false
          const open = collapsible ? !collapsed[plane.key] : true
          return (
            <div key={plane.key}>
              <SectionHeader
                label={plane.label}
                collapsible={collapsible}
                open={open}
                onToggle={() => toggle(plane.key)}
              />
              {open && plane.items.map((it) => <NavItem key={it.path} {...it} />)}
            </div>
          )
        })}

        {/* SUPPORT — always shown */}
        <SectionHeader label={t('nav.sectionHelp')} collapsible={false} />
        <NavItem path="/help" label={t('nav.help')} icon={LifeBuoy} />
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-white/5">
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
