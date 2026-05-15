import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

const ToastContext = createContext(null)

const TYPE_COLORS = {
  success: '#16a34a',
  error: '#dc2626',
  warning: '#d97706',
  info: '#2563eb',
}

function ToastItem({ toast, onDismiss }) {
  return (
    <div
      className="toast-enter bg-white rounded-lg shadow-lg pointer-events-auto flex overflow-hidden"
      style={{ width: 280, borderLeft: `4px solid ${TYPE_COLORS[toast.type] || TYPE_COLORS.info}` }}
    >
      <div className="flex-1 p-3">
        <p className="text-[13px] text-gray-800 leading-snug">{toast.message}</p>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="px-2 text-gray-400 hover:text-gray-600 transition-colors self-start pt-3"
      >
        <X size={13} />
      </button>
    </div>
  )
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counterRef = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback((message, type = 'info') => {
    const id = ++counterRef.current
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => dismiss(id), 4000)
  }, [dismiss])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {createPortal(
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
          {toasts.map((t) => (
            <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be inside ToastProvider')
  return ctx
}
