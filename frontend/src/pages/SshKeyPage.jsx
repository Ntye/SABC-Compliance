import { useState } from 'react'
import { KeyRound, RefreshCw, ShieldCheck, AlertTriangle, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { getSshKey, rotateSshKey, setSshKeySchedule } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import Spinner from '../components/common/Spinner.jsx'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'
import { badge } from '../lib/tw.js'

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

// Per-node rotation outcome → badge variant.
const NODE_STATUS = {
  rotated:              'success',
  rotated_old_present:  'warning',
  ready:                'success',
  verify_failed:        'danger',
  unreachable:          'gray',
}

export default function SshKeyPage() {
  const t = useT()
  const toast = useToast()
  const { data, loading, refetch } = useApi(getSshKey)

  const [rotating, setRotating] = useState(false)
  const [confirmRotate, setConfirmRotate] = useState(false)
  const [report, setReport] = useState(null)

  const [enabled, setEnabled] = useState(false)
  const [days, setDays] = useState(90)
  const [savingSched, setSavingSched] = useState(false)
  const [schedInit, setSchedInit] = useState(false)

  // Seed the schedule form once the status loads.
  if (data && !schedInit) {
    setEnabled(!!data.schedule?.enabled)
    setDays(data.schedule?.days || 90)
    setSchedInit(true)
  }

  async function doRotate() {
    setConfirmRotate(false)
    setRotating(true)
    setReport(null)
    try {
      const res = await rotateSshKey()
      setReport(res)
      if (res.rotated) {
        toast(t('sshKey.rotatedOk', { n: res.reachable ?? 0 }), 'success')
      } else {
        toast(res.reason || t('sshKey.rotateAborted'), 'error')
      }
      await refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRotating(false)
    }
  }

  async function saveSchedule() {
    setSavingSched(true)
    try {
      await setSshKeySchedule({ enabled, days: Number(days) || 90 })
      toast(t('sshKey.scheduleSaved'), 'success')
      await refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSavingSched(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
          <KeyRound size={17} className="text-brand" />
          {t('sshKey.title')}
        </h2>
        <p className="text-[12px] text-gray-400 mt-0.5 max-w-2xl">{t('sshKey.subtitle')}</p>
      </div>

      {/* Current key */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h3 className="text-[13px] font-semibold text-gray-800 mb-3">{t('sshKey.currentTitle')}</h3>
        {loading && !data ? (
          <div className="h-20 bg-gray-100 animate-pulse rounded-lg" />
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[12px]">
            <div className="col-span-2 flex items-center gap-2">
              <dt className="text-gray-400 w-28">{t('sshKey.fingerprint')}</dt>
              <dd className="font-mono text-gray-800 break-all">{data?.fingerprint || '—'}</dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="text-gray-400 w-28">{t('sshKey.type')}</dt>
              <dd className="text-gray-700">{data?.type || '—'}{data?.bits ? ` · ${data.bits} bit` : ''}</dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="text-gray-400 w-28">{t('sshKey.nodes')}</dt>
              <dd className="text-gray-700">{data?.node_count ?? '—'}</dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="text-gray-400 w-28">{t('sshKey.lastRotated')}</dt>
              <dd className="text-gray-700">{data?.last_rotated ? fmtDate(data.last_rotated) : t('sshKey.never')}</dd>
            </div>
            <div className="flex items-center gap-2">
              <dt className="text-gray-400 w-28">{t('sshKey.nextDue')}</dt>
              <dd className="text-gray-700">{data?.next_due ? fmtDate(data.next_due) : '—'}</dd>
            </div>
          </dl>
        )}

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => setConfirmRotate(true)}
            disabled={rotating}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand/90 disabled:opacity-50"
          >
            {rotating ? <Spinner size={13} /> : <RefreshCw size={13} />}
            {rotating ? t('sshKey.rotating') : t('sshKey.rotateNow')}
          </button>
          {data?.has_previous && (
            <span className="inline-flex items-center gap-1 text-[11px] text-gray-400" title={t('sshKey.prevHint')}>
              <ShieldCheck size={12} /> {t('sshKey.prevKept')}
            </span>
          )}
        </div>
      </div>

      {/* Automatic rotation schedule */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h3 className="text-[13px] font-semibold text-gray-800 mb-1 flex items-center gap-1.5">
          <Clock size={14} className="text-gray-400" /> {t('sshKey.scheduleTitle')}
        </h3>
        <p className="text-[11px] text-gray-400 mb-4">{t('sshKey.scheduleHint')}</p>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            <span className="text-[13px] text-gray-800">{t('sshKey.enableAuto')}</span>
          </label>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('sshKey.everyDays')}</label>
            <input
              type="number" min={1} value={days}
              onChange={(e) => setDays(e.target.value)}
              disabled={!enabled}
              className="w-28 px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>
          <button
            onClick={saveSchedule}
            disabled={savingSched}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 text-gray-700 text-[13px] font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {savingSched ? <Spinner size={12} /> : null}
            {t('sshKey.saveSchedule')}
          </button>
        </div>
      </div>

      {/* Rotation report */}
      {report && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
            {report.rotated
              ? <CheckCircle2 size={15} className="text-green-500" />
              : <AlertTriangle size={15} className="text-amber-500" />}
            <h3 className="text-[13px] font-semibold text-gray-800">
              {report.rotated ? t('sshKey.reportOk') : t('sshKey.reportAborted')}
            </h3>
            <span className="text-[11px] text-gray-400 ml-auto">
              {t('sshKey.reportCounts', {
                reachable: report.reachable ?? 0,
                unreachable: report.unreachable ?? 0,
              })}
            </span>
          </div>
          {!report.rotated && report.reason && (
            <p className="px-5 py-2 text-[12px] text-amber-700 bg-amber-50">{report.reason}</p>
          )}
          <div className="divide-y divide-gray-50">
            {(report.nodes || []).map((n) => (
              <div key={n.node_id} className="px-5 py-2.5 flex items-center justify-between text-[12px]">
                <span className="font-medium text-gray-700">{n.hostname}</span>
                <span className="flex items-center gap-2">
                  {n.error && <span className="text-[11px] text-gray-400">{n.error}</span>}
                  <span className={badge(NODE_STATUS[n.status] || 'gray')}>
                    {t(`sshKey.node_${n.status}`)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmRotate}
        title={t('sshKey.confirmTitle')}
        message={t('sshKey.confirmMsg')}
        confirmLabel={t('sshKey.rotateNow')}
        onConfirm={doRotate}
        onCancel={() => setConfirmRotate(false)}
      />
    </div>
  )
}
