import { useEffect, useRef, useState } from 'react'
import { CheckCircle, ChevronDown, ChevronUp, RefreshCw, XCircle } from 'lucide-react'
import { cancelJob, getJob, jobWsUrl, listJobs } from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, btnSm, logLineClass } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import CopyButton from '../components/common/CopyButton.jsx'

function duration(start, end) {
  const ms = new Date(end || Date.now()) - new Date(start)
  if (ms < 0) return '—'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

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
      {status === 'running' && <Spinner size={9} />}
      {status === 'success' && <CheckCircle size={9} />}
      {status === 'failed' && <XCircle size={9} />}
      {t(`jobs.status.${status}`) || status}
    </span>
  )
}

function LogPanel({ jobId, initialLogs, isRunning, t }) {
  const [lines, setLines] = useState(initialLogs || [])
  const [wsConnected, setWsConnected] = useState(false)
  const bottomRef = useRef(null)
  const wsRef = useRef(null)
  const toast = useToast()

  useEffect(() => {
    if (!isRunning) {
      setLines(initialLogs || [])
      return
    }
    const ws = new WebSocket(jobWsUrl(jobId))
    wsRef.current = ws
    setLines([])

    ws.onopen = () => setWsConnected(true)
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      setLines((prev) => [...prev, msg])
    }
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

function JobRow({ job: initial, onRefresh }) {
  const [job, setJob] = useState(initial)
  const [expanded, setExpanded] = useState(false)
  const [logs, setLogs] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const toast = useToast()
  const t = useT()

  const isRunning = job.status === 'running' || job.status === 'pending'

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

  const serviceLabel = job.service
    ? job.service.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : '—'

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <div className="flex items-center gap-4 px-4 py-3 bg-white hover:bg-gray-50 transition-colors">
        <button onClick={handleExpand} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-gray-900">{serviceLabel}</span>
            <StatusBadge status={job.status} t={t} />
          </div>
          <div className="flex items-center gap-4 mt-0.5">
            <span className="inline-flex items-center gap-1 text-[11px] text-gray-400 font-mono">
              {job.id.slice(0, 8)}
              <CopyButton
                text={job.id}
                size={11}
                className="text-gray-300 hover:text-gray-500"
                onResult={(ok) => toast(ok ? t('common.copied') : t('common.copyFailed'), ok ? 'success' : 'error')}
              />
            </span>
            {job.node_hostname && (
              <span className="text-[11px] text-gray-500">→ {job.node_hostname}</span>
            )}
          </div>
        </div>

        <div className="text-right flex-shrink-0 hidden sm:block">
          <p className="text-[11px] text-gray-500">{fmt(job.started_at)}</p>
          <p className="text-[10px] text-gray-400">{duration(job.started_at, job.completed_at)}</p>
        </div>

        {isRunning && (
          <button
            onClick={handleCancel}
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

export default function JobsPage() {
  const t = useT()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [fetchError, setFetchError] = useState(null)

  async function load() {
    try {
      const data = await listJobs(100)
      setJobs(data)
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

  const running = jobs.filter((j) => j.status === 'running' || j.status === 'pending')
  const done = jobs.filter((j) => j.status !== 'running' && j.status !== 'pending')

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
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
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-[13px]">{t('jobs.noJobs')}</p>
          <p className="text-[11px] mt-1">{t('jobs.noJobsDesc')}</p>
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
                  <JobRow key={j.id} job={j} onRefresh={handleRefresh} />
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
                  <JobRow key={j.id} job={j} onRefresh={handleRefresh} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
