import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowRightLeft, Eye, Palette, ShieldCheck, X } from 'lucide-react'
import { clearApiKey, getStoredApiKey } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useLang } from '../../context/LangContext.jsx'
import ThemePanel from '../settings/ThemePanel.jsx'
import ActivateModal from '../auth/ActivateModal.jsx'

const PAGE_KEY = {
  '/overview':       'header.pageOverview',
  '/nodes':          'header.pageNodes',
  '/add-vm':         'header.pageAddVm',
  '/infrastructure': 'header.pageInfrastructure',
  '/jobs':           'header.pageJobs',
  '/compliance':     'header.pageCompliance',
  '/rules':          'header.pageRules',
  '/keys':           'header.pageKeys',
  '/audit':          'header.pageAudit',
  '/profiles':       'header.pageProfiles',
}

function resolvePageKey(pathname) {
  if (PAGE_KEY[pathname]) return PAGE_KEY[pathname]
  // prefix match — longest wins (e.g. /compliance/123 → pageCompliance)
  const match = Object.keys(PAGE_KEY)
    .filter((k) => pathname.startsWith(k + '/'))
    .sort((a, b) => b.length - a.length)[0]
  return match ? PAGE_KEY[match] : 'header.pageOverview'
}

export default function Header() {
  const location = useLocation()
  const toast    = useToast()
  const { lang, t, setLang } = useLang()

  const [panelOpen,    setPanelOpen]    = useState(false)
  const [activateOpen, setActivateOpen] = useState(false)
  // tick lets us re-render after the modal applies a key (localStorage write)
  const [, setTick] = useState(0)

  const titleKey  = resolvePageKey(location.pathname)
  const title     = t(titleKey)
  const storedKey = getStoredApiKey()
  const maskedKey = storedKey ? storedKey.slice(0, 8) + '••••••••' : ''

  function handleDeactivate() {
    clearApiKey()
    toast(t('header.deactivated'), 'success')
    setTick((n) => n + 1)
  }

  return (
    <>
      <header className="h-14 flex-shrink-0 bg-white border-b border-gray-100 flex items-center justify-between px-6">
        <h1 className="text-[15px] font-semibold text-gray-900">{title}</h1>

        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div className="flex items-center gap-0.5 rounded-lg overflow-hidden border border-gray-200 mr-1">
            {['en', 'fr'].map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2.5 py-1 text-[11px] font-semibold uppercase transition-colors ${
                  lang === l
                    ? 'bg-brand text-white'
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
                }`}
              >
                {l}
              </button>
            ))}
          </div>

          {/* API key status */}
          {!storedKey ? (
            <button
              onClick={() => setActivateOpen(true)}
              className="flex items-center gap-1.5 pl-2 pr-3 py-1 rounded-full bg-amber-50 border border-amber-200 hover:bg-amber-100 transition-colors"
              title={t('header.viewOnlyTooltip')}
            >
              <Eye size={12} className="text-amber-700" />
              <span className="text-[11px] font-semibold text-amber-800">{t('header.viewOnly')}</span>
            </button>
          ) : (
            <div className="flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-full bg-green-50 border border-green-200">
              <ShieldCheck size={12} className="text-green-700" />
              <span className="text-[11px] font-semibold text-green-800">{t('header.active')}</span>
              <span className="text-[11px] font-mono text-green-900/70 ml-1">{maskedKey}</span>
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

          {/* Theme / appearance panel trigger */}
          <button
            onClick={() => setPanelOpen(true)}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors ml-1"
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
