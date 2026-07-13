import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRightLeft, Eye, Palette, Search, ShieldCheck, X } from 'lucide-react'
import { clearApiKey, getStoredApiKey, getUserRole, getUsername } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useLang } from '../../context/LangContext.jsx'
import { usePosture } from '../../hooks/usePosture.js'
import ThemePanel from '../settings/ThemePanel.jsx'
import ActivateModal from '../auth/ActivateModal.jsx'
import NotificationBell from './NotificationBell.jsx'

// Human labels + accent for each role. The badge is informational — it tells
// the user what they can do; it never hides views.
const ROLE_META = {
  admin:    { label: 'Platform Admin',       cls: 'bg-brand/15 text-brand border-brand/30' },
  operator: { label: 'Security Ops',         cls: 'bg-amber-500/15 text-amber-700 border-amber-300' },
  readonly: { label: 'Compliance Auditor',   cls: 'bg-gray-100 text-gray-500 border-gray-200' },
}

function scoreColor(s) {
  return s >= 90 ? 'text-green-600' : s >= 70 ? 'text-amber-600' : 'text-red-600'
}

function Kpi({ value, label, accent, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className="flex items-baseline gap-1.5 px-1 disabled:cursor-default"
      title={label}
    >
      <span className={`text-[15px] font-bold leading-none ${accent || 'text-gray-800'}`}>{value}</span>
      <span className="text-[10px] text-gray-400 uppercase tracking-wide hidden lg:inline">{label}</span>
    </button>
  )
}

export default function Header() {
  const navigate = useNavigate()
  const toast    = useToast()
  const { lang, t, setLang } = useLang()
  const { data: posture } = usePosture()

  const [panelOpen,    setPanelOpen]    = useState(false)
  const [activateOpen, setActivateOpen] = useState(false)
  const [, setTick] = useState(0)

  const storedKey = getStoredApiKey()
  const maskedKey = storedKey ? storedKey.slice(0, 8) + '••••••••' : ''
  const role = getUserRole() || 'readonly'
  const roleMeta = ROLE_META[role] || ROLE_META.readonly
  const username = getUsername()

  function handleDeactivate() {
    clearApiKey()
    toast(t('header.deactivated'), 'success')
    setTick((n) => n + 1)
  }

  return (
    <>
      <header className="h-14 flex-shrink-0 bg-white border-b border-gray-100 flex items-center gap-4 px-6">
        {/* Global posture KPIs — always visible, one glance at fleet health */}
        <div className="flex items-center gap-4">
          <Kpi
            value={posture ? `${posture.globalScore}` : '—'}
            label={t('topbar.globalScore')}
            accent={posture ? scoreColor(posture.globalScore) : 'text-gray-300'}
            onClick={() => navigate('/overview')}
          />
          <span className="w-px h-5 bg-gray-100" />
          <Kpi
            value={posture ? posture.totalNodes : '—'}
            label={t('topbar.nodes')}
            onClick={() => navigate('/nodes')}
          />
          <span className="w-px h-5 bg-gray-100" />
          <Kpi
            value={posture ? posture.activeAlerts : '—'}
            label={t('topbar.activeAlerts')}
            accent={posture && posture.activeAlerts > 0 ? 'text-red-600' : 'text-gray-800'}
            onClick={() => navigate('/detection')}
          />
        </div>

        {/* Search — routes to the most relevant view */}
        <form
          onSubmit={(e) => { e.preventDefault(); navigate('/nodes') }}
          className="flex-1 max-w-md hidden md:block"
        >
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-300" />
            <input
              placeholder={t('topbar.search')}
              onFocusCapture={() => {}}
              className="w-full bg-gray-50 border border-gray-100 rounded-lg pl-8 pr-3 py-1.5 text-[12px] outline-none focus:border-brand focus:bg-white"
            />
          </div>
        </form>

        <div className="flex items-center gap-2 ml-auto">
          {/* Language toggle */}
          <div className="flex items-center gap-0.5 rounded-lg overflow-hidden border border-gray-200">
            {['en', 'fr'].map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2.5 py-1 text-[11px] font-semibold uppercase transition-colors ${
                  lang === l ? 'bg-brand text-white' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
                }`}
              >
                {l}
              </button>
            ))}
          </div>

          {/* API key status (write access) */}
          {!storedKey ? (
            <button
              onClick={() => setActivateOpen(true)}
              className="flex items-center gap-1.5 pl-2 pr-3 py-1 rounded-full bg-amber-50 border border-amber-200 hover:bg-amber-100 transition-colors"
              title={t('header.viewOnlyTooltip')}
            >
              <Eye size={12} className="text-amber-700" />
              <span className="text-[11px] font-semibold text-amber-800">{t('topbar.viewOnly')}</span>
            </button>
          ) : (
            <div className="flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-full bg-green-50 border border-green-200">
              <ShieldCheck size={12} className="text-green-700" />
              <span className="text-[11px] font-mono text-green-900/70">{maskedKey}</span>
              <button
                onClick={() => setActivateOpen(true)}
                className="p-1 rounded-full hover:bg-green-100 text-green-700"
                title={t('header.overrideTooltip')}
              >
                <ArrowRightLeft size={11} />
              </button>
              <button
                onClick={handleDeactivate}
                className="p-1 rounded-full hover:bg-green-100 text-green-700"
                title={t('header.deactivate')}
              >
                <X size={11} />
              </button>
            </div>
          )}

          {/* Role badge + user — informational, never hides views */}
          <div className="flex items-center gap-2 pl-1">
            <span className={`px-2 py-[3px] rounded-full text-[10px] font-semibold border ${roleMeta.cls}`}>
              {roleMeta.label}
            </span>
            {username && (
              <span className="text-[12px] font-medium text-gray-700 hidden lg:inline">{username}</span>
            )}
          </div>

          {/* Platform notifications (enforcement / scan outcomes) */}
          <NotificationBell />

          {/* Theme / appearance */}
          <button
            onClick={() => setPanelOpen(true)}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            title={t('header.settings')}
          >
            <Palette size={14} />
          </button>
        </div>
      </header>

      {panelOpen    && <ThemePanel onClose={() => setPanelOpen(false)} />}
      {activateOpen && <ActivateModal onClose={() => { setActivateOpen(false); setTick((n) => n + 1) }} />}
    </>
  )
}
