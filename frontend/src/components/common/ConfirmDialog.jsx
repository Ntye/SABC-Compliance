import { createPortal } from 'react-dom'
import Button from './Button.jsx'

export default function ConfirmDialog({ open, title, message, onConfirm, onCancel, confirmLabel = 'Confirm', danger = false }) {
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h3 className="text-[15px] font-semibold text-gray-900 mb-2">{title}</h3>
        {message && <p className="text-[13px] text-gray-500 mb-5">{message}</p>}
        <div className="flex gap-2 justify-end">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
