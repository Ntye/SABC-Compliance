import { badge } from '../../lib/tw.js'

export default function Badge({ variant, children }) {
  return <span className={badge(variant)}>{children}</span>
}
