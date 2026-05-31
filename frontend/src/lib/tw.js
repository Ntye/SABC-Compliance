export const btn = (primary = true) =>
  primary
    ? 'inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium transition-all hover:bg-brand/90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed'
    : 'inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 bg-transparent text-gray-900 text-[13px] font-medium transition-all hover:bg-surface-page active:scale-[0.98] disabled:opacity-50'

export const btnSm = (primary = true) =>
  primary
    ? 'inline-flex items-center gap-[5px] px-3 py-[5px] rounded-md bg-brand text-white text-[11px] font-medium transition-all hover:bg-brand/90 active:scale-[0.98]'
    : 'inline-flex items-center gap-[5px] px-3 py-[5px] rounded-md border border-gray-200 bg-transparent text-gray-900 text-[11px] font-medium transition-all hover:bg-surface-page active:scale-[0.98]'

export const btnDanger =
  'inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-red-600/30 text-red-600 text-[13px] font-medium transition-all hover:bg-red-600/5 active:scale-[0.98]'

export const btnDangerSm =
  'inline-flex items-center gap-[5px] px-3 py-[5px] rounded-md border border-red-600/30 text-red-600 text-[11px] font-medium transition-all hover:bg-red-600/5 active:scale-[0.98]'

export const badge = (variant) => {
  const base =
    'inline-flex items-center px-2 py-[3px] rounded-full text-[10px] font-medium'
  const variants = {
    success: `${base} bg-green-600/15 text-green-700`,
    warning: `${base} bg-amber-500/15 text-amber-700`,
    danger: `${base} bg-red-600/15 text-red-700`,
    info: `${base} bg-blue-600/15 text-blue-700`,
    gray: `${base} bg-gray-100 text-gray-500`,
    admin: `${base} bg-brand/15 text-brand`,
    operator: `${base} bg-amber-500/15 text-amber-700`,
    readonly: `${base} bg-gray-100 text-gray-500`,
    cis: `${base} bg-blue-600/15 text-blue-700`,
    iso27001: `${base} bg-green-600/15 text-green-700`,
    'pci-dss': `${base} bg-amber-500/15 text-amber-700`,
    RedHat: `${base} bg-amber-100 text-amber-800`,
    Debian: `${base} bg-blue-100 text-blue-800`,
  }
  return variants[variant] || variants.gray
}

export const scoreColor = (n) =>
  n >= 90 ? 'text-green-600' : n >= 70 ? 'text-amber-600' : 'text-red-600'

export const scoreBarColor = (n) =>
  n >= 90 ? 'bg-green-600' : n >= 70 ? 'bg-amber-500' : 'bg-red-600'

export const dotColor = (status) =>
  ({
    reachable: 'bg-green-500',
    provisioned: 'bg-green-500',
    unreachable: 'bg-red-500',
    registered: 'bg-gray-400',
    running: 'bg-amber-500',
    success: 'bg-green-500',
    failed: 'bg-red-500',
    pending: 'bg-gray-400',
    cancelled: 'bg-gray-400',
  })[status] || 'bg-gray-400'

export const methodBadge = (method) =>
  ({
    GET: badge('info'),
    POST: badge('success'),
    DELETE: badge('danger'),
    PATCH: badge('warning'),
  })[method] || badge('gray')

export const statusCodeColor = (code) =>
  code < 300 ? 'text-green-600' : code < 500 ? 'text-amber-600' : 'text-red-600'

export const logLevelColor = (level) =>
  ({
    error: 'text-console-danger',
    success: 'text-console-success',
    warning: 'text-console-warning',
    task: 'text-console-task',
    system: 'text-console-accent',
    info: 'text-console-text',
  })[level] || 'text-console-text'

// Shared classifier for a single Ansible/job log line. Used by both the Jobs
// page and the Infrastructure install drawer so output looks identical.
// Plain lines default to the soft-white console-text (not the faint gray that
// used to be near-invisible on the black background).
export const logLineClass = (l) => {
  if (!l) return 'text-console-text'
  if (l.level === 'system') return 'text-console-accent font-semibold mt-1'
  const line = l.line || ''
  if (!line.trim()) return 'text-console-faint'
  if (/FATAL|FAILED|ERROR|unreachable=[1-9]|failed=[1-9]/.test(line)) return 'text-console-danger'
  if (/^WARNING|\bWARN\b|warning:|skipping:|\.\.\.ignoring/.test(line)) return 'text-console-warning'
  if (/^changed:|changed=[1-9]/.test(line)) return 'text-console-task'
  if (/^ok:|PLAY RECAP|^\s*ok=/.test(line)) return 'text-console-success'
  if (/^TASK|^PLAY|^RUNNING HANDLER/.test(line)) return 'text-console-text font-semibold'
  return 'text-console-text'
}
