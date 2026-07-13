import { useCallback, useEffect, useRef, useState } from 'react'
import { Bell, CheckCheck, ShieldCheck, Activity, Info } from 'lucide-react'
import {
  listNotifications, markAllNotificationsRead, markNotificationRead,
} from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'

const POLL_MS = 15000

const SEV_COLOR = {
  success: 'bg-green-500',
  error: 'bg-red-500',
  info: 'bg-blue-500',
}

const KIND_ICON = {
  enforcement: ShieldCheck,
  scan: Activity,
}

function timeAgo(iso, t) {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return t('notifications.justNow')
  const m = Math.round(s / 60)
  if (m < 60) return t('notifications.minutesAgo', { n: m })
  const h = Math.round(m / 60)
  if (h < 24) return t('notifications.hoursAgo', { n: h })
  return new Date(iso).toLocaleDateString()
}

// Header bell: polls the platform notification feed (enforcement jobs launched
// from the Tiers page + their chained verification scans). New unread entries
// also surface as toasts so the outcome is visible without opening the panel.
export default function NotificationBell() {
  const t = useT()
  const toast = useToast()
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const seenRef = useRef(null) // null until the first load — never toast old items

  const load = useCallback(async () => {
    try {
      const list = await listNotifications({ limit: 30 })
      const arr = Array.isArray(list) ? list : []
      if (seenRef.current !== null) {
        for (const n of arr) {
          if (!n.is_read && !seenRef.current.has(n.id)) {
            toast(n.title, n.severity === 'error' ? 'error' : 'success')
          }
        }
      }
      seenRef.current = new Set(arr.map((n) => n.id))
      setItems(arr)
    } catch {
      /* silent — the bell must never break the header */
    }
  }, [toast])

  useEffect(() => {
    load()
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [load])

  const unread = items.filter((n) => !n.is_read).length

  async function readOne(n) {
    if (n.is_read) return
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
    try { await markNotificationRead(n.id) } catch { /* re-synced on next poll */ }
  }

  async function readAll() {
    setItems((prev) => prev.map((x) => ({ ...x, is_read: true })))
    try { await markAllNotificationsRead() } catch { /* re-synced on next poll */ }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-1.5 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
        title={t('notifications.title')}
      >
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-0.5 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center leading-none">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-[340px] bg-white border border-gray-100 rounded-xl shadow-lg z-40 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
              <span className="text-[12px] font-semibold text-gray-800">{t('notifications.title')}</span>
              {unread > 0 && (
                <button
                  onClick={readAll}
                  className="inline-flex items-center gap-1 text-[11px] text-brand hover:underline"
                >
                  <CheckCheck size={11} /> {t('notifications.markAllRead')}
                </button>
              )}
            </div>
            <div className="max-h-[380px] overflow-y-auto">
              {items.length === 0 ? (
                <p className="px-4 py-8 text-center text-[12px] text-gray-400">{t('notifications.empty')}</p>
              ) : (
                items.map((n) => {
                  const Icon = KIND_ICON[n.kind] || Info
                  return (
                    <button
                      key={n.id}
                      onClick={() => readOne(n)}
                      className={`w-full text-left px-4 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50/60 flex gap-2.5 ${
                        n.is_read ? 'opacity-60' : ''
                      }`}
                    >
                      <span className="relative flex-shrink-0 mt-0.5">
                        <Icon size={15} className="text-gray-400" />
                        <span className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${SEV_COLOR[n.severity] || SEV_COLOR.info}`} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[12px] font-medium text-gray-800 leading-snug">{n.title}</span>
                        {n.message && (
                          <span className="block text-[11px] text-gray-500 mt-0.5 leading-snug">{n.message}</span>
                        )}
                        <span className="block text-[10px] text-gray-400 mt-1">{timeAgo(n.created_at, t)}</span>
                      </span>
                      {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0 mt-1.5" />}
                    </button>
                  )
                })
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
