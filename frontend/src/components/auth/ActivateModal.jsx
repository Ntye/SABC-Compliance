import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, Copy, KeyRound, X } from 'lucide-react'
import { createApiKey, getUserRole, getUsername, setApiKey } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useT } from '../../context/LangContext.jsx'
import Button from '../common/Button.jsx'

// Modal opened from the header "Activate" pill. Two flows:
//   1. Generate (admin only) → POST /auth/keys → display once → Apply
//   2. Paste an existing key (any user) → Apply
// Apply writes to localStorage so subsequent requests include X-API-Key.

export default function ActivateModal({ onClose }) {
  const t       = useT()
  const toast   = useToast()
  const role    = getUserRole()
  const isAdmin = role === 'admin'

  const today      = new Date().toISOString().slice(0, 10)
  const defaultName = `${getUsername() || 'user'}-${today}`

  const [tab,        setTab]        = useState(isAdmin ? 'generate' : 'paste')
  const [name,       setName]       = useState(defaultName)
  const [keyRole,    setKeyRole]    = useState(role === 'admin' ? 'operator' : (role || 'operator'))
  const [generated,  setGenerated]  = useState('')
  const [pasted,     setPasted]     = useState('')
  const [busy,       setBusy]       = useState(false)
  const [copied,     setCopied]     = useState(false)

  async function handleGenerate() {
    if (!name.trim()) {
      toast(t('activate.nameRequired'), 'error')
      return
    }
    setBusy(true)
    try {
      const result = await createApiKey(name.trim(), keyRole)
      setGenerated(result.api_key)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function handleCopy(value) {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function handleApply(value) {
    if (!value) return
    setApiKey(value)
    toast(t('activate.applied'), 'success')
    onClose()
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <KeyRound size={16} className="text-brand" />
            <h3 className="text-[14px] font-semibold text-gray-900">{t('activate.title')}</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={16} />
          </button>
        </div>

        <p className="px-5 pt-4 text-[12px] text-gray-500 leading-relaxed">
          {t('activate.intro')}
        </p>

        {isAdmin && (
          <div className="flex gap-1 px-5 pt-3">
            <button
              onClick={() => { setTab('generate'); setGenerated('') }}
              className={`px-3 py-1.5 text-[11px] font-semibold rounded-md transition-colors ${
                tab === 'generate' ? 'bg-brand text-white' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {t('activate.tabGenerate')}
            </button>
            <button
              onClick={() => setTab('paste')}
              className={`px-3 py-1.5 text-[11px] font-semibold rounded-md transition-colors ${
                tab === 'paste' ? 'bg-brand text-white' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {t('activate.tabPaste')}
            </button>
          </div>
        )}

        <div className="px-5 py-4 space-y-3">
          {tab === 'generate' && !generated && (
            <>
              <label className="block">
                <span className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">{t('activate.nameLabel')}</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full px-3 py-2 text-[13px] border border-gray-200 rounded-md focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">{t('activate.roleLabel')}</span>
                <select
                  value={keyRole}
                  onChange={(e) => setKeyRole(e.target.value)}
                  className="mt-1 w-full px-3 py-2 text-[13px] border border-gray-200 rounded-md focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                >
                  <option value="readonly">{t('activate.roleReadonly')}</option>
                  <option value="operator">{t('activate.roleOperator')}</option>
                  <option value="admin">{t('activate.roleAdmin')}</option>
                </select>
              </label>
              <Button variant="primary" loading={busy} onClick={handleGenerate} className="w-full">
                {t('activate.generateBtn')}
              </Button>
            </>
          )}

          {tab === 'generate' && generated && (
            <div className="space-y-3">
              <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2">
                <p className="text-[11px] font-semibold text-amber-800">{t('activate.warningTitle')}</p>
                <p className="text-[11px] text-amber-700 mt-0.5">{t('activate.warningBody')}</p>
              </div>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 px-3 py-2 text-[11px] font-mono bg-gray-50 border border-gray-200 rounded-md break-all">
                  {generated}
                </code>
                <button
                  onClick={() => handleCopy(generated)}
                  className="px-3 rounded-md border border-gray-200 hover:bg-gray-50 text-gray-500"
                  title={t('activate.copy')}
                >
                  {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
                </button>
              </div>
              <Button variant="primary" onClick={() => handleApply(generated)} className="w-full">
                {t('activate.applyBtn')}
              </Button>
            </div>
          )}

          {tab === 'paste' && (
            <>
              <label className="block">
                <span className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">{t('activate.pasteLabel')}</span>
                <input
                  type="password"
                  value={pasted}
                  onChange={(e) => setPasted(e.target.value)}
                  placeholder="bdc_..."
                  className="mt-1 w-full px-3 py-2 text-[13px] font-mono border border-gray-200 rounded-md focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                />
              </label>
              <Button variant="primary" disabled={!pasted.trim()} onClick={() => handleApply(pasted.trim())} className="w-full">
                {t('activate.applyBtn')}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
