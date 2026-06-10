import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle, ChevronRight, Clock, RefreshCw, Search, XCircle } from 'lucide-react'
import { cancelJob, getJob, jobWsUrl, listJobs, listNodes } from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, btnSm, logLineClass } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import CopyButton from '../components/common/CopyButton.jsx'

// ── Service type → human-readable label ──────────────────────────────────────

const SERVICE_LABELS = {
  'puppet-master':  'Puppet Master Install',
  'puppet-agent':   'Puppet Agent Install',
  'wazuh-manager':  'Wazuh Manager Install',
  'wazuh-agent':    'Wazuh Agent Install',
  'provision':      'VM Provision (Add VM)',
  'inspec-verify':  'Compliance Scan (InSpec)',
}

function serviceLabel(type) {
  return SERVICE_LABELS[type] ||
    (type ? type.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : '—')
}

// ── Duration formatters ───────────────────────────────────────────────────────

const DURATION_UNITS = [
  { k: 'y',  s: 31536000 },
  { k: 'mo', s: 2592000  },
  { k: 'd',  s: 86400    },
  { k: 'h',  s: 3600     },
  { k: 'm',  s: 60       },
  { k: 's',  s: 1        },
]

function fmtDuration(totalSeconds) {
  if (!totalSeconds || totalSeconds <= 0) return '0s'
  let rem = Math.floor(totalSeconds)
  const parts = []
  for (const u of DURATION_UNITS) {
    const v = Math.floor(rem / u.s)
    rem -= v * u.s
    if (v > 0) parts.push(`${v}${u.k}`)
  }
  return parts.slice(0, 3).join(' ') || '0s'
}

// Backend stores UTC datetimes without timezone suffix. Append 'Z' so the
// browser always parses them as UTC rather than local time.
function utcDate(iso) {
  if (!iso) return null
  return new Date(/[Zz]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z')
}

function duration(start, end) {
  const ms = (end ? utcDate(end) : new Date()) - utcDate(start)
  if (ms < 0) return '—'
  return fmtDuration(Math.floor(ms / 1000))
}

function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.floor((Date.now() - utcDate(iso)) / 1000)
  if (s < 60)  return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60)  return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24)  return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7)   return `${d}d ago`
  const w = Math.floor(d / 7)
  if (w < 5)   return `${w}w ago`
  const mo = Math.floor(d / 30)
  if (mo < 12) return `${mo}mo ago`
  return `${Math.floor(d / 365)}y ago`
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status, t }) {
  const map = {
    pending:   'bg-gray-100 text-gray-500',
    running:   'bg-blue-50 text-blue-600',
    success:   'bg-green-50 text-green-700',
    failed:    'bg-red-50 text-red-600',
    cancelled: 'bg-amber-50 text-amber-600',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${map[status] || map.pending}`}>
      {status === 'running'   && <Spinner size={9} />}
      {status === 'success'   && <CheckCircle size={9} />}
      {status === 'failed'    && <XCircle size={9} />}
      {t(`jobs.status.${status}`) || status}
    </span>
  )
}

// ── Log panel ─────────────────────────────────────────────────────────────────

function LogPanel({ jobId, initialLogs, isRunning, t }) {
  const [lines, setLines] = useState(initialLogs || [])
  const [wsConnected, setWsConnected] = useState(false)
  const bottomRef = useRef(null)
  const toast = useToast()

  useEffect(() => {
    if (!isRunning) {
      setLines(initialLogs || [])
      return
    }
    const ws = new WebSocket(jobWsUrl(jobId))
    ws.onopen = () => setWsConnected(true)
    ws.onmessage = (e) => setLines((prev) => [...prev, JSON.parse(e.data)])
    ws.onerror = () => setWsConnected(false)
    ws.onclose = () => setWsConnected(false)
    return () => ws.close()
  }, [jobId, isRunning])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div className="mt-3 rounded-xl overflow-hidden bg-console-bg border border-white/5">
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
        <span className="text-[10px] font-mono text-console-muted uppercase tracking-wider">
          {isRunning
            ? wsConnected ? t('jobs.liveOutput') : t('jobs.connecting')
            : t('jobs.output')}
        </span>
        <div className="flex items-center gap-3">
          {isRunning && wsConnected && <Spinner size={10} className="text-console-accent" />}
          {lines.length > 0 && (
            <CopyButton
              text={lines.map((l) => l.line ?? '').join('\n')}
              size={11}
              label={t('jobs.copyOutput')}
              className="text-console-muted hover:text-console-text"
              onResult={(ok) => toast(ok ? t('common.copied') : t('common.copyFailed'), ok ? 'success' : 'error')}
            />
          )}
        </div>
      </div>
      <div className="h-64 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed">
        {lines.length === 0 && (
          <span className="text-console-faint italic">{t('jobs.noOutput')}</span>
        )}
        {lines.map((l, i) => (
          <div key={i} className={logLineClass(l)}>{l.line || ' '}</div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Job row ───────────────────────────────────────────────────────────────────

function JobRow({ job: initial, nodeMap, onRefresh }) {
  const [job, setJob] = useState(initial)
  const [expanded, setExpanded] = useState(false)
  const [logs, setLogs] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const toast = useToast()
  const t = useT()

  const isRunning = job.status === 'running' || job.status === 'pending'
  const label = serviceLabel(job.type)
  const nodeDisplay = nodeMap?.[job.node_id]?.hostname || job.node_id?.slice(0, 8) || null

  async function handleExpand() {
    if (!expanded && logs === null) {
      try {
        const detail = await getJob(job.id)
        setJob(detail)
        setLogs(detail.logs || [])
      } catch (err) {
        toast(err.message, 'error')
        return
      }
    }
    setExpanded((v) => !v)
  }

  async function handleCancel() {
    setCancelling(true)
    try {
      const updated = await cancelJob(job.id)
      setJob(updated)
      onRefresh()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 transition-colors cursor-pointer" onClick={handleExpand}>
        <ChevronRight
          size={14}
          className={`text-gray-400 flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-gray-900">{label}</span>
            <StatusBadge status={job.status} t={t} />
          </div>
          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
            <span className="inline-flex items-center gap-1 text-[11px] text-gray-400 font-mono">
              {job.id.slice(0, 8)}
              <CopyButton
                text={job.id}
                size={11}
                className="text-gray-300 hover:text-gray-500"
                onResult={(ok) => toast(ok ? t('common.copied') : t('common.copyFailed'), ok ? 'success' : 'error')}
              />
            </span>
            {nodeDisplay && (
              <span className="text-[11px] text-gray-500">→ {nodeDisplay}</span>
            )}
          </div>
        </div>

        <div className="text-right flex-shrink-0 hidden sm:flex flex-col items-end gap-0.5">
          <p className="text-[11px] text-gray-500">{timeAgo(job.started_at || job.created_at)}</p>
          <span className="inline-flex items-center gap-1 text-[10px] text-gray-400">
            <Clock size={10} />
            {duration(job.started_at || job.created_at, job.finished_at)}
          </span>
        </div>

        {isRunning && (
          <button
            onClick={(e) => { e.stopPropagation(); handleCancel() }}
            disabled={cancelling}
            className={btnSm(false)}
          >
            {cancelling && <Spinner size={11} />}
            {t('jobs.cancel')}
          </button>
        )}
      </div>

      {expanded && (
        <div className="px-4 pb-4 bg-gray-50 border-t border-gray-100">
          <LogPanel
            jobId={job.id}
            initialLogs={logs}
            isRunning={isRunning}
            t={t}
          />
        </div>
      )}
    </div>
  )
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({ jobs, filters, onChange, t }) {
  const { query, taskType, status } = filters

  // Distinct task types from loaded jobs
  const taskTypes = useMemo(() => {
    const seen = new Set()
    jobs.forEach((j) => seen.add(j.type))
    return [...seen].sort()
  }, [jobs])

  // Count per status
  const counts = useMemo(() => {
    const c = { all: jobs.length, success: 0, failed: 0, cancelled: 0 }
    jobs.forEach((j) => {
      if (j.status === 'success')   c.success++
      if (j.status === 'failed')    c.failed++
      if (j.status === 'cancelled') c.cancelled++
    })
    return c
  }, [jobs])

  const segButtons = [
    { key: 'all',       label: t('jobs.statusAll'),       cls: 'text-gray-700' },
    { key: 'success',   label: t('jobs.statusSuccess'),   cls: 'text-green-700' },
    { key: 'failed',    label: t('jobs.statusFailed'),    cls: 'text-red-600' },
    { key: 'cancelled', label: t('jobs.statusCancelled'), cls: 'text-amber-600' },
  ]

  return (
    <div className="flex flex-wrap items-center gap-2 mb-5">
      {/* Search */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg flex-1 min-w-[160px] max-w-[280px]">
        <Search size={13} className="text-gray-400 flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => onChange({ ...filters, query: e.target.value })}
          placeholder={t('jobs.searchPlaceholder')}
          className="flex-1 text-[12px] outline-none bg-transparent text-gray-700 placeholder-gray-400"
        />
      </div>

      {/* Task type dropdown */}
      <div className="relative">
        <select
          value={taskType}
          onChange={(e) => onChange({ ...filters, taskType: e.target.value })}
          className="appearance-none pl-3 pr-7 py-1.5 text-[12px] bg-white border border-gray-200 rounded-lg outline-none focus:border-brand text-gray-700 cursor-pointer"
        >
          <option value="all">{t('jobs.allTasks')}</option>
          {taskTypes.map((type) => (
            <option key={type} value={type}>{serviceLabel(type)}</option>
          ))}
        </select>
        <ChevronRight size={11} className="absolute right-2 top-1/2 -translate-y-1/2 rotate-90 text-gray-400 pointer-events-none" />
      </div>

      {/* Status segmented control */}
      <div className="flex items-center bg-white border border-gray-200 rounded-lg overflow-hidden">
        {segButtons.map(({ key, label, cls }) => (
          <button
            key={key}
            onClick={() => onChange({ ...filters, status: key })}
            className={`px-3 py-1.5 text-[11px] font-medium transition-colors ${
              status === key
                ? 'bg-gray-100 ' + cls
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            {label}
            {counts[key] !== undefined && (
              <span className="ml-1 text-[10px] text-gray-400">{counts[key]}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function JobsPage() {
  const t = useT()
  const [jobs, setJobs] = useState([])
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [fetchError, setFetchError] = useState(null)
  const [filters, setFilters] = useState({ query: '', taskType: 'all', status: 'all' })

  async function load() {
    try {
      const [jobsData, nodesData] = await Promise.all([listJobs(100), listNodes()])
      setJobs(jobsData)
      setNodes(nodesData)
      setFetchError(null)
    } catch (err) {
      setFetchError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  function handleRefresh() {
    setRefreshing(true)
    load()
  }

  // Build node map for hostname lookup
  const nodeMap = useMemo(() => {
    const m = {}
    nodes.forEach((n) => { m[n.id] = n })
    return m
  }, [nodes])

  // Apply filters
  const filtered = useMemo(() => {
    const { query, taskType, status } = filters
    const q = query.toLowerCase()
    return jobs.filter((j) => {
      if (status !== 'all' && j.status !== status) return false
      if (taskType !== 'all' && j.type !== taskType) return false
      if (q) {
        const node = nodeMap[j.node_id]
        const hay = [serviceLabel(j.type), j.id, node?.hostname || '', node?.ip || ''].join(' ').toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [jobs, filters, nodeMap])

  const running = filtered.filter((j) => j.status === 'running' || j.status === 'pending')
  const done    = filtered.filter((j) => j.status !== 'running' && j.status !== 'pending')

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900">{t('jobs.title')}</h2>
          <p className="text-[12px] text-gray-400 mt-0.5">{t('jobs.subtitle')}</p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className={btnSm(false)}>
          {refreshing ? <Spinner size={11} /> : <RefreshCw size={11} />}
          {t('common.refresh')}
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : fetchError ? (
        <div className="p-4 border border-red-200 bg-red-50 rounded-xl">
          <p className="text-[12px] text-red-600">{fetchError}</p>
        </div>
      ) : (
        <>
          <FilterBar jobs={jobs} filters={filters} onChange={setFilters} t={t} />

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              {jobs.length === 0 ? (
                <>
                  <p className="text-[13px]">{t('jobs.noJobs')}</p>
                  <p className="text-[11px] mt-1">{t('jobs.noJobsDesc')}</p>
                </>
              ) : (
                <p className="text-[13px]">{t('jobs.noMatch')}</p>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {running.length > 0 && (
                <section>
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    {t('jobs.running', { count: running.length })}
                  </p>
                  <div className="space-y-2">
                    {running.map((j) => (
                      <JobRow key={j.id} job={j} nodeMap={nodeMap} onRefresh={handleRefresh} />
                    ))}
                  </div>
                </section>
              )}
              {done.length > 0 && (
                <section>
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    {t('jobs.history')}
                  </p>
                  <div className="space-y-2">
                    {done.map((j) => (
                      <JobRow key={j.id} job={j} nodeMap={nodeMap} onRefresh={handleRefresh} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
