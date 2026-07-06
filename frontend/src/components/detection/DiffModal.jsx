import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, FileDiff } from 'lucide-react'
import { getConfigBlob } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import Spinner from '../common/Spinner.jsx'

// Line-level LCS diff → unified rows. Guarded against pathological sizes so a
// huge file can't lock the UI (falls back to a plain two-block view).
const MAX_DIFF_LINES = 2500

function diffLines(aText, bText) {
  const A = aText.split('\n')
  const B = bText.split('\n')
  const n = A.length
  const m = B.length
  if (n > MAX_DIFF_LINES || m > MAX_DIFF_LINES) return null
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const rows = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (A[i] === B[j]) { rows.push({ t: 'ctx', text: A[i], ln: i + 1, rn: j + 1 }); i++; j++ }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { rows.push({ t: 'del', text: A[i], ln: i + 1 }); i++ }
    else { rows.push({ t: 'add', text: B[j], rn: j + 1 }); j++ }
  }
  while (i < n) { rows.push({ t: 'del', text: A[i], ln: i + 1 }); i++ }
  while (j < m) { rows.push({ t: 'add', text: B[j], rn: j + 1 }); j++ }
  return rows
}

const ROW_STYLES = {
  add: 'bg-green-50 text-green-800',
  del: 'bg-red-50 text-red-800',
  ctx: 'text-gray-600',
}
const ROW_SIGN = { add: '+', del: '-', ctx: ' ' }

function actorLabel(actor) {
  if (!actor) return null
  return actor.username || actor.comm || actor.exe || (actor.auid != null ? `auid ${actor.auid}` : null)
}

export default function DiffModal({ event, onClose }) {
  const t = useT()
  const [loading, setLoading] = useState(true)
  const [before, setBefore] = useState(null)   // { text, is_binary, truncated } | null
  const [after, setAfter] = useState(null)
  const [beforeMissing, setBeforeMissing] = useState(false)
  const [afterMissing, setAfterMissing] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      const fetchBlob = async (hash, setBlob, setMissing) => {
        if (!hash) { setBlob(null); return }
        try {
          const blob = await getConfigBlob(hash)
          if (!cancelled) setBlob(blob)
        } catch (_) {
          if (!cancelled) setMissing(true)
        }
      }
      await Promise.all([
        fetchBlob(event.prev_hash, setBefore, setBeforeMissing),
        fetchBlob(event.new_hash, setAfter, setAfterMissing),
      ])
      if (!cancelled) setLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [event.prev_hash, event.new_hash])

  // ESC closes.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const binary = (before && before.is_binary) || (after && after.is_binary)
  const noContent =
    (!before && (event.prev_hash ? true : false) && beforeMissing) &&
    (!after && afterMissing)
  const rows = (!loading && !binary && !noContent)
    ? diffLines(before?.text || '', after?.text || '')
    : null
  const truncated = (before && before.truncated) || (after && after.truncated)
  const who = actorLabel(event.actor)

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-4xl mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-gray-100">
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold text-gray-900 flex items-center gap-2">
              <FileDiff size={16} className="text-brand" />
              {t('detection.diffTitle')}
            </h3>
            <p className="text-[12px] font-mono text-gray-500 mt-1 truncate" title={event.path}>
              {event.hostname ? `${event.hostname}: ` : ''}{event.path}
            </p>
            {who && (
              <p className="text-[11px] text-gray-400 mt-0.5">
                {t('detection.diffActorLine')}: <span className="font-medium text-gray-600">{who}</span>
                {event.actor?.auid != null && <span className="text-gray-400"> · uid {event.actor.auid}</span>}
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 shrink-0 ml-3" aria-label={t('detection.close')}>
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-auto flex-1 p-4">
          {loading ? (
            <div className="flex items-center gap-2 text-[13px] text-gray-500 py-8 justify-center">
              <Spinner size={14} /> {t('detection.diffLoading')}
            </div>
          ) : binary ? (
            <p className="text-[13px] text-gray-500 py-6 text-center">{t('detection.diffBinary')}</p>
          ) : noContent ? (
            <p className="text-[13px] text-gray-500 py-6 text-center">{t('detection.diffNoContent')}</p>
          ) : rows && rows.length === 0 ? (
            <p className="text-[13px] text-gray-500 py-6 text-center">{t('detection.diffUnchanged')}</p>
          ) : rows ? (
            <>
              {!event.prev_hash && (
                <p className="text-[11px] text-gray-400 mb-2">{t('detection.diffNoPrev')}</p>
              )}
              <div className="rounded-lg border border-gray-100 overflow-x-auto">
                <table className="w-full text-[11.5px] font-mono leading-[1.5]">
                  <tbody>
                    {rows.map((r, idx) => (
                      <tr key={idx} className={ROW_STYLES[r.t]}>
                        <td className="select-none text-right pr-2 pl-3 text-gray-300 w-10 align-top">{r.ln || ''}</td>
                        <td className="select-none text-right pr-2 text-gray-300 w-10 align-top">{r.rn || ''}</td>
                        <td className="select-none pr-2 text-gray-400 align-top">{ROW_SIGN[r.t]}</td>
                        <td className="pr-3 whitespace-pre-wrap break-all align-top">{r.text || ' '}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            // LCS bailed out (file too large): plain before/after blocks.
            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase mb-1">{t('detection.diffBefore')}</div>
                <pre className="text-[11px] font-mono bg-gray-50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-[50vh]">{before?.text || '—'}</pre>
              </div>
              <div>
                <div className="text-[10px] font-semibold text-gray-500 uppercase mb-1">{t('detection.diffAfter')}</div>
                <pre className="text-[11px] font-mono bg-gray-50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-[50vh]">{after?.text || '—'}</pre>
              </div>
            </div>
          )}
          {truncated && (
            <p className="text-[11px] text-amber-600 mt-2">{t('detection.diffTruncated')}</p>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
