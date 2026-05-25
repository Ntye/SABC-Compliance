import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Copy, Key, Palette } from 'lucide-react'
import { getStoredApiKey, initApiKey, setApiKey } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useLang } from '../../context/LangContext.jsx'
import ThemePanel from '../settings/ThemePanel.jsx'

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
}

export default function Header() {
  const location = useLocation()
  const toast    = useToast()
  const { lang, t, setLang } = useLang()

  const [copying,      setCopying]      = useState(false)
  const [initing,      setIniting]      = useState(false)
  const [panelOpen,    setPanelOpen]    = useState(false)

  const titleKey = PAGE_KEY[location.pathname] || 'header.pageOverview'
  const title    = t(titleKey)

  const storedKey = getStoredApiKey()
  const maskedKey = storedKey ? storedKey.slice(0, 8) + '••••••••' : t('header.noApiKey')

  async function handleCopy() {
    if (!storedKey) return
    await navigator.clipboard.writeText(storedKey)
    setCopying(true)
    setTimeout(() => setCopying(false), 1500)
  }

  async function handleInit() {
    setIniting(true)
    try {
      const result = await initApiKey()
      setApiKey(result.api_key)
      toast(t('header.apiKeyCreated', { key: result.api_key }), 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setIniting(false)
    }
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

          {/* API key display */}
          <span className="text-[12px] font-mono text-gray-400">{maskedKey}</span>
          <button
            onClick={handleCopy}
            disabled={!storedKey}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-30"
            title={t('header.copyApiKey')}
          >
            <Copy size={13} className={copying ? 'text-green-600' : ''} />
          </button>
          <button
            onClick={handleInit}
            disabled={initing}
            className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            title={t('header.initApiKey')}
          >
            <Key size={13} />
          </button>

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

      {panelOpen && <ThemePanel onClose={() => setPanelOpen(false)} />}
    </>
  )
}
