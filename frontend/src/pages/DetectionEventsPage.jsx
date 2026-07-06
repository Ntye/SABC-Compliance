import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Activity, ChevronDown, FileDiff, FileWarning, RefreshCw, ShieldOff } from 'lucide-react'
import { jobWsUrl, listDetectionEvents, listNodes } from '../lib/api.js'
import { useT } from '../context/LangContext.jsx'
import { badge, btnSm } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import DiffModal from '../components/detection/DiffModal.jsx'

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function shortHash(h) {
  return h ? h.slice(0, 10) : '—'
}

// Badge explaining the gateway's suppression decision for an event.
function SuppressionBadge({ event, t }) {
  if (!event.suppressed) {
    return <span className={badge('danger')}>{t('detection.live')}</span>
  }
  const labels = {
    remediation_pending: t('detection.suppressedRemediation'),
    puppet_run: t('detection.suppressedPuppetRun'),
    baseline: t('detection.baseline'),
  }
  return (
    <span className={badge('gray')} title={event.suppress_reason || ''}>
      <ShieldOff size={9} className="inline mr-0.5 -mt-px" />
      {labels[event.suppress_reason] || t('detection.suppressed')}
    </span>
  )
}

function EventTypeBadge({ type }) {
  const styles = {
    created: 'warning',
    modified: 'warning',
    deleted: 'danger',
    moved: 'warning',
    baseline: 'gray',
  }
  return <span className={badge(styles[type] || 'gray')}>{type}</span>
}

function ActorCell({ actor }) {
  if (!actor) return <span className="text-gray-300">—</span>
  // Prefer the resolved login name ("who"), falling back to process/uid.
  const label = actor.username || actor.comm || actor.exe || `auid ${actor.auid}`
  const uid = actor.auid ?? actor.uid
  return (
    <span className="font-mono text-[11px] text-gray-600" title={JSON.stringify(actor)}>
      {label}
      {uid !== undefined && uid !== null && (
        <span className="text-gray-400"> · uid {uid}</span>
      )}
    </span>
  )
}

export default function DetectionEventsPage() {
  const t = useT()
  const [searchParams, setSearchParams] = useSearchParams()
  const [events, setEvents] = useState([])
  const [nodes, setNodes] = useState([])
  const [nodeFilter, setNodeFilter] = useState(searchParams.get('node') || '')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [live, setLive] = useState(false)
  const [diffEvent, setDiffEvent] = useState(null)
  const wsRef = useRef(null)

  async function load(filter = nodeFilter) {
    try {
      const [evts, ns] = await Promise.all([
        listDetectionEvents({ nodeId: filter || null, limit: 200 }),
        listNodes(),
      ])
      setEvents(evts)
      setNodes(ns)
    } catch (_) {}
    finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { setLoading(true); load(nodeFilter) }, [nodeFilter])

  // Poll as a safety net; the WebSocket feed below prepends events live.
  useEffect(() => {
    const timer = setInterval(() => load(), 30000)
    return () => clearInterval(timer)
  }, [nodeFilter])

  // Live feed: the gateway broadcasts every stored event on the
  // "detection-events" channel.
  useEffect(() => {
    let ws
    try {
      ws = new WebSocket(jobWsUrl('detection-events'))
      wsRef.current = ws
      ws.onopen = () => setLive(true)
      ws.onclose = () => setLive(false)
      ws.onerror = () => setLive(false)
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.channel !== 'detection' || !msg.data?.event_id) return
          if (msg.phase !== 'detected' && msg.phase !== 'suppressed') return
          if (nodeFilter && msg.node_id !== nodeFilter) return
          setEvents((prev) => {
            if (prev.some((ev) => ev.id === msg.data.event_id)) return prev
            const evt = {
              id: msg.data.event_id,
              node_id: msg.node_id,
              hostname: msg.hostname,
              path: msg.data.path,
              event_type: msg.data.event_type,
              timestamp: msg.timestamp,
              prev_hash: msg.data.prev_hash,
              new_hash: msg.data.new_hash,
              puppet_running: msg.data.puppet_running,
              actor: msg.data.actor,
              suppressed: msg.data.suppressed,
              suppress_reason: msg.data.suppress_reason,
              remediation_event_id: null,
              created_at: msg.timestamp,
            }
            return [evt, ...prev].slice(0, 300)
          })
        } catch (_) {}
      }
    } catch (_) {}
    return () => { try { ws?.close() } catch (_) {} }
  }, [nodeFilter])

  const liveCount = useMemo(() => events.filter((e) => !e.suppressed).length, [events])
  const suppressedCount = events.length - liveCount

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
            <Activity size={17} className="text-brand" />
            {t('detection.title')}
            {live && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                {t('detection.liveFeed')}
              </span>
            )}
          </h2>
          <p className="text-[12px] text-gray-400 mt-0.5">{t('detection.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              value={nodeFilter}
              onChange={(e) => {
                setNodeFilter(e.target.value)
                setSearchParams(e.target.value ? { node: e.target.value } : {}, { replace: true })
              }}
              className="appearance-none pl-3 pr-8 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white text-gray-700"
            >
              <option value="">{t('detection.allNodes')}</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.hostname}</option>
              ))}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
          <button onClick={() => { setRefreshing(true); load() }} disabled={refreshing} className={btnSm(false)}>
            {refreshing ? <Spinner size={11} /> : <RefreshCw size={11} />}
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {/* Counters */}
      <div className="flex items-center gap-3 mb-4">
        <span className="text-[11px] text-gray-500">
          <span className="font-semibold text-gray-800">{events.length}</span> {t('detection.eventsShown')}
        </span>
        <span className={badge('danger')}>{liveCount} {t('detection.live')}</span>
        <span className={badge('gray')}>{suppressedCount} {t('detection.suppressed')}</span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-12 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      ) : events.length === 0 ? (
        <EmptyState
          icon={FileWarning}
          title={t('detection.emptyTitle')}
          description={t('detection.emptyDesc')}
        />
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100">
                  {[
                    t('detection.colNode'), t('detection.colPath'), t('detection.colType'),
                    t('detection.colTime'), t('detection.colActor'), t('detection.colHashes'),
                    t('detection.colDecision'), t('detection.colRemediation'),
                  ].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50/60">
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <Link to={`/nodes/${e.node_id}`} className="font-medium text-gray-800 hover:text-brand hover:underline">
                        {e.hostname}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-gray-700 max-w-[260px] truncate" title={e.path}>
                      {e.path || '—'}
                    </td>
                    <td className="px-4 py-2.5"><EventTypeBadge type={e.event_type} /></td>
                    <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap" title={e.created_at}>
                      {fmtDate(e.timestamp)}
                    </td>
                    <td className="px-4 py-2.5"><ActorCell actor={e.actor} /></td>
                    <td className="px-4 py-2.5 font-mono text-[10px] text-gray-400 whitespace-nowrap"
                        title={`${e.prev_hash || '∅'} → ${e.new_hash || '∅'}`}>
                      {shortHash(e.prev_hash)} → {shortHash(e.new_hash)}
                    </td>
                    <td className="px-4 py-2.5"><SuppressionBadge event={e} t={t} /></td>
                    <td className="px-4 py-2.5">
                      {e.event_type === 'baseline' || (!e.prev_hash && !e.new_hash) ? (
                        <span className="text-gray-300">—</span>
                      ) : (
                        <button
                          onClick={() => setDiffEvent(e)}
                          className="inline-flex items-center gap-1 text-[11px] text-brand hover:underline"
                        >
                          <FileDiff size={11} />
                          {t('detection.viewDiff')}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {diffEvent && <DiffModal event={diffEvent} onClose={() => setDiffEvent(null)} />}
    </div>
  )
}
