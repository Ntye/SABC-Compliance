import { dotColor } from '../../lib/tw.js'

export default function StatusDot({ status, size = 8 }) {
  return (
    <span
      className={`inline-block rounded-full ${dotColor(status)}`}
      style={{ width: size, height: size, flexShrink: 0 }}
    />
  )
}
