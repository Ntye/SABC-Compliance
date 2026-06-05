import { useState } from 'react'
import { AlertTriangle, CheckCircle, Info, Wrench, XCircle } from 'lucide-react'
import { checkNodeDns, fixNodeDns } from '../../lib/api.js'
import { useT } from '../../context/LangContext.jsx'
import Spinner from '../common/Spinner.jsx'

function CheckRow({ label, check, canFix, fixing, fixResult, onFix, t }) {
  const isNull  = check.ok === null
  const hasTarget = Boolean(check.to)
  const needsFix = check.ok !== true && (check.ok === false || hasTarget)

  const Icon  = check.ok === true  ? CheckCircle
              : check.ok === false ? XCircle
              : isNull && hasTarget ? AlertTriangle
              : Info
  const color = check.ok === true  ? 'text-green-600'
              : check.ok === false ? 'text-red-500'
              : isNull && hasTarget ? 'text-amber-500'
              : 'text-blue-400'
  const nullTag = hasTarget
    ? t('nodes.dnsModal.checkFailed')
    : t('nodes.dnsModal.serviceNotSet')

  return (
    <div className="px-3 py-2.5 border-b border-gray-100 last:border-0">
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 flex-shrink-0 ${color}`}>
          <Icon size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-medium text-gray-800">{label}</span>
            {isNull && (
              <span className={`text-[10px] font-medium ${hasTarget ? 'text-amber-500' : 'text-blue-500'}`}>
                {nullTag}
              </span>
            )}
          </div>
          <div className="text-[11px] text-gray-400 font-mono truncate">
            {check.from_host} → {check.to || '?'}
          </div>
          <div className="text-[11px] text-gray-500 mt-0.5">{check.description}</div>
        </div>

        {canFix && needsFix && (
          <button
            onClick={onFix}
            disabled={fixing}
            className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-60 transition-colors flex-shrink-0"
          >
            {fixing ? <Spinner size={10} /> : <Wrench size={10} />}
            {fixing ? t('nodes.dnsModal.fixing') : t('nodes.dnsModal.fixAuto')}
          </button>
        )}
      </div>

      {fixResult && (
        <div className={`ml-[22px] mt-2 px-3 py-2 rounded-lg text-[11px] ${fixResult.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {fixResult.ok
            ? <>{t('nodes.dnsModal.fixApplied')}{fixResult.entry && <span className="font-mono ml-1">{fixResult.entry}</span>}</>
            : <>{t('nodes.dnsModal.fixFailed')}{fixResult.error && <span className="ml-1 opacity-80">{fixResult.error}</span>}</>
          }
        </div>
      )}

      {!canFix && !check.to && isNull && (
        <div className="ml-[22px] mt-1 text-[11px] text-blue-500">
          {t('nodes.dnsModal.serviceNotConfiguredShort')}
        </div>
      )}
    </div>
  )
}

export default function DnsModal({ node, onClose, onRefetch }) {
  const t = useT()
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [fixing, setFixing]     = useState({})    // { checkKey: true }
  const [fixResults, setFixResults] = useState({}) // { checkKey: { ok, entry?, error? } }

  async function run() {
    setLoading(true)
    setError(null)
    setFixResults({})
    try {
      const data = await checkNodeDns(node.id)
      setResult(data)
      onRefetch?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleFix(checkKey) {
    setFixing((f) => ({ ...f, [checkKey]: true }))
    try {
      const data = await fixNodeDns(node.id, [checkKey])
      const r = data.results?.[checkKey] ?? { ok: false, error: 'No result' }
      setFixResults((prev) => ({ ...prev, [checkKey]: r }))
    } catch (err) {
      setFixResults((prev) => ({ ...prev, [checkKey]: { ok: false, error: err.message } }))
    } finally {
      setFixing((f) => ({ ...f, [checkKey]: false }))
    }
  }

  const CHECK_LABELS = {
    backend_to_node: t('nodes.dnsModal.checkPlatformToNode'),
    node_to_backend: t('nodes.dnsModal.checkNodeToPlatform'),
    node_to_puppet:  t('nodes.dnsModal.checkNodeToPuppet'),
    node_to_wazuh:   t('nodes.dnsModal.checkNodeToWazuh'),
  }

  const checks = result
    ? Object.entries(result.checks).map(([key, val]) => ({ key, ...val }))
    : []

  const actionableChecks = checks.filter((c) => c.ok !== true)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="text-[14px] font-semibold text-gray-900">{t('nodes.dnsModal.title')}</h3>
            <p className="text-[11px] text-gray-400 mt-0.5">
              <span className="font-mono">{node.hostname}</span>
              {node.fqdn && node.fqdn !== node.hostname && (
                <span className="ml-1 text-gray-300">({node.fqdn})</span>
              )}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-[18px] leading-none">&times;</button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {/* Run / Re-run button */}
          <button
            onClick={run}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2 text-[12px] font-medium rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-60 transition-colors"
          >
            {loading && <Spinner size={12} />}
            {loading
              ? t('nodes.dnsModal.running')
              : result
                ? t('nodes.dnsModal.rerunChecks')
                : t('nodes.dnsModal.runChecks')}
          </button>

          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          {/* Results */}
          {result && (
            <>
              {result.all_ok ? (
                <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-lg">
                  <CheckCircle size={13} className="text-green-600" />
                  <span className="text-[12px] text-green-700 font-medium">{t('nodes.dnsModal.allPassed')}</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 rounded-lg">
                  <AlertTriangle size={12} className="text-amber-500 flex-shrink-0" />
                  <span className="text-[11px] text-amber-700">
                    {t('nodes.dnsModal.failSummary', { n: actionableChecks.length, total: checks.length })}
                  </span>
                </div>
              )}

              <div className="rounded-xl border border-gray-100 overflow-hidden">
                {checks.map((c) => (
                  <CheckRow
                    key={c.key}
                    label={CHECK_LABELS[c.key] || c.key}
                    check={c}
                    canFix={c.ok !== true && Boolean(c.to)}
                    fixing={!!fixing[c.key]}
                    fixResult={fixResults[c.key] ?? null}
                    onFix={() => handleFix(c.key)}
                    t={t}
                  />
                ))}
              </div>

              {!result.all_ok && (
                <p className="text-[10px] text-gray-400">{t('nodes.dnsModal.rerunHint')}</p>
              )}
            </>
          )}

          {/* Idle state */}
          {!result && !loading && (
            <p className="text-[12px] text-gray-400 text-center py-4">
              {t('nodes.dnsModal.idle')}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
