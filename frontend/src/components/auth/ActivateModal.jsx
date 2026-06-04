import { useState } from 'react'
import { createPortal } from 'react-dom'
import { KeyRound, X } from 'lucide-react'
import { setApiKey } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useT } from '../../context/LangContext.jsx'
import Button from '../common/Button.jsx'

// Opened from the header when the user wants to temporarily override their
// personal API key with a higher-privilege key.
export default function ActivateModal({ onClose }) {
  const t     = useT()
  const toast = useToast()

  const [pasted, setPasted] = useState('')

  function handleApply() {
    const val = pasted.trim()
    if (!val) return
    setApiKey(val)
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

        <div className="px-5 py-4 space-y-3">
          <label className="block">
            <span className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">{t('activate.pasteLabel')}</span>
            <input
              type="password"
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="sabc_..."
              className="mt-1 w-full px-3 py-2 text-[13px] font-mono border border-gray-200 rounded-md focus:border-brand focus:ring-1 focus:ring-brand outline-none"
            />
          </label>
          <Button variant="primary" disabled={!pasted.trim()} onClick={handleApply} className="w-full">
            {t('activate.applyBtn')}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
