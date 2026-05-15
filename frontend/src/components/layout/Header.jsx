import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Copy, Key } from 'lucide-react'
import { getStoredApiKey, initApiKey, setApiKey } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'

const PAGE_TITLES = {
  '/overview': 'Overview',
  '/nodes': 'Node Registry',
  '/add-vm': 'Add VM',
  '/jobs': 'Jobs',
  '/compliance': 'Compliance',
  '/rules': 'Puppet Rules',
  '/keys': 'API Keys',
  '/audit': 'Audit Log',
}

export default function Header() {
  const location = useLocation()
  const toast = useToast()
  const [copying, setCopying] = useState(false)
  const [initing, setIniting] = useState(false)

  const title = PAGE_TITLES[location.pathname] || 'BdC Compliance'
  const storedKey = getStoredApiKey()
  const maskedKey = storedKey ? storedKey.slice(0, 8) + '••••••••' : 'No API key'

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
      toast(`API key created: ${result.api_key}`, 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setIniting(false)
    }
  }

  return (
    <header className="h-14 flex-shrink-0 bg-white border-b border-gray-100 flex items-center justify-between px-6">
      <h1 className="text-[15px] font-semibold text-gray-900">{title}</h1>
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-mono text-gray-400">{maskedKey}</span>
        <button
          onClick={handleCopy}
          disabled={!storedKey}
          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-30"
          title="Copy API key"
        >
          <Copy size={13} className={copying ? 'text-green-600' : ''} />
        </button>
        <button
          onClick={handleInit}
          disabled={initing}
          className="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          title="Init API key"
        >
          <Key size={13} />
        </button>
      </div>
    </header>
  )
}
