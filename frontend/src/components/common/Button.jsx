import { btn, btnDanger, btnDangerSm, btnSm } from '../../lib/tw.js'
import Spinner from './Spinner.jsx'

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  onClick,
  type = 'button',
  className = '',
}) {
  let cls
  if (variant === 'danger') cls = size === 'sm' ? btnDangerSm : btnDanger
  else cls = size === 'sm' ? btnSm(variant === 'primary') : btn(variant === 'primary')

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`${cls} ${className}`}
    >
      {loading ? <Spinner size={size === 'sm' ? 10 : 14} /> : null}
      {children}
    </button>
  )
}
