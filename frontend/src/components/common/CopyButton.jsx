import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { copyText } from '../../lib/clipboard.js'

// Click-to-copy icon button. Works over plain HTTP (IP access) via the
// execCommand fallback in copyText(). Shows a brief check mark on success.
//
// Props:
//   text      — string to copy
//   size      — icon size (default 12)
//   className — extra classes for the button
//   label     — optional text shown next to the icon
//   onResult  — optional (ok: boolean) => void callback (e.g. to toast)
export default function CopyButton({ text, size = 12, className = '', label, onResult }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy(e) {
    e?.stopPropagation?.()
    const ok = await copyText(text)
    onResult?.(ok)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`inline-flex items-center gap-1 transition-colors ${className}`}
      title="Copy"
    >
      {copied ? <Check size={size} className="text-green-500" /> : <Copy size={size} />}
      {label && <span className="text-[11px]">{copied ? 'Copied' : label}</span>}
    </button>
  )
}
