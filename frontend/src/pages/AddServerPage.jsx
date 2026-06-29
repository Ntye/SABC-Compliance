import { useEffect, useRef, useState } from 'react'
import { CheckCircle, ChevronDown, ChevronRight, Download, Globe, HardDriveDownload, Terminal, XCircle } from 'lucide-react'
import { downloadSetupScript, jobWsUrl, registerNode } from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, logLineClass } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import CopyButton from '../components/common/CopyButton.jsx'

const DEFAULT_FORM = {
  hostname: '',
  ip: '',
  ssh_port: '22',
  ssh_user: 'ansible',
  ssh_key_path: '',
  description: '',
  tags: '',
}

export default function AddServerPage() {
  const toast = useToast()
  const t = useT()
  const [form, setForm] = useState(DEFAULT_FORM)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [platformUrl, setPlatformUrl] = useState(() => window.location.origin)

  // detect-agents job log state
  const [detectJobId, setDetectJobId] = useState(null)
  const [detectLogs, setDetectLogs] = useState([])
  const [detectDone, setDetectDone] = useState(false)
  const wsRef = useRef(null)
  const logEndRef = useRef(null)

  function set(field) {
    return (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  // Auto-scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [detectLogs])

  // Connect to WebSocket for detect job
  useEffect(() => {
    if (!detectJobId) return
    const url = jobWsUrl(detectJobId)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'log' && msg.line) {
          setDetectLogs((prev) => [...prev, msg.line])
        } else if (msg.type === 'status') {
          if (msg.status === 'success' || msg.status === 'failed' || msg.status === 'cancelled') {
            setDetectDone(true)
            ws.close()
          }
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => setDetectDone(true)
    ws.onclose = () => setDetectDone(true)

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [detectJobId])

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
    setDetectJobId(null)
    setDetectLogs([])
    setDetectDone(false)
    try {
      const payload = {
        hostname: form.hostname.trim(),
        ip: form.ip.trim(),
        ssh_port: parseInt(form.ssh_port, 10) || 22,
        ssh_user: form.ssh_user.trim() || 'ansible',
        ssh_key_path: form.ssh_key_path.trim() || null,
        description: form.description.trim() || null,
        tags: form.tags ? form.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : [],
      }
      const node = await registerNode(payload)
      setResult({ success: true, node })
      toast(`Node '${node.hostname}' registered (${node.os_name || node.os_family || 'Unknown OS'})`, 'success')
      if (node.detect_job_id) {
        setDetectJobId(node.detect_job_id)
      } else {
        setTimeout(() => {
          setForm(DEFAULT_FORM)
          setResult(null)
        }, 2500)
      }
    } catch (err) {
      setResult({ success: false, error: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  function handleReset() {
    setForm(DEFAULT_FORM)
    setResult(null)
    setDetectJobId(null)
    setDetectLogs([])
    setDetectDone(false)
  }

  const curlCmd = `curl -k -sSL ${platformUrl}/api/nodes/bootstrap | sudo bash`
  const airgapCmd = 'sudo bash setup-node.sh'

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h2 className="text-[18px] font-semibold text-gray-900">{t('addServer.title')}</h2>

      {/* ── Zone 1: Registration form ── */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 max-w-2xl">
        <h3 className="text-[14px] font-semibold text-gray-800 mb-5">{t('addServer.cardTitle')}</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Row: hostname + IP (always visible) */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                {t('addServer.hostname')} <span className="text-red-500">{t('addServer.required')}</span>
              </label>
              <input
                required
                value={form.hostname}
                onChange={set('hostname')}
                placeholder="web-01"
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                {t('addServer.ipAddress')} <span className="text-red-500">{t('addServer.required')}</span>
              </label>
              <input
                required
                value={form.ip}
                onChange={set('ip')}
                placeholder="10.0.0.5"
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
              />
            </div>
          </div>

          {/* Advanced setup toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1.5 text-[11px] font-medium text-gray-400 hover:text-gray-600 transition-colors"
          >
            {showAdvanced ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {t('addServer.advancedSetup')}
          </button>

          {showAdvanced && (
            <div className="space-y-4 border-t border-gray-100 pt-4">
              {/* Row: SSH port + SSH user */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addServer.sshPort')}</label>
                  <input
                    type="number"
                    value={form.ssh_port}
                    onChange={set('ssh_port')}
                    placeholder="22"
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addServer.sshUser')}</label>
                  <input
                    value={form.ssh_user}
                    onChange={set('ssh_user')}
                    placeholder="ansible"
                    className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                  />
                </div>
              </div>

              {/* SSH key path */}
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                  {t('addServer.sshKeyPath')} <span className="text-gray-400">{t('addServer.sshKeyHint')}</span>
                </label>
                <input
                  value={form.ssh_key_path}
                  onChange={set('ssh_key_path')}
                  placeholder="./keys/ansible_id_rsa"
                  className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all font-mono"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addServer.description')}</label>
                <input
                  value={form.description}
                  onChange={set('description')}
                  placeholder="Production web server"
                  className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                />
              </div>

              {/* Tags */}
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                  {t('addServer.tags')} <span className="text-gray-400">{t('addServer.tagsHint')}</span>
                </label>
                <input
                  value={form.tags}
                  onChange={set('tags')}
                  placeholder="production, web, dmz"
                  className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                />
              </div>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className={`${btn(true)} w-full justify-center`}
          >
            {submitting && <Spinner size={14} />}
            {submitting ? t('addServer.registering') : t('addServer.register')}
          </button>
        </form>

        {/* Inline success + detect log */}
        {result && result.success && (
          <div className="mt-4 space-y-3">
            <div className="flex items-start gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-green-800">{t('addServer.successTitle')}</p>
                <p className="text-[12px] text-green-700 mt-0.5">
                  {result.node.hostname} · {result.node.os_name || result.node.os_family || 'Unknown OS'} · {result.node.ip}
                </p>
              </div>
              {detectDone && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="flex-shrink-0 text-[11px] text-green-600 hover:text-green-800 underline"
                >
                  {t('common.close')}
                </button>
              )}
            </div>

            {/* Agent detection log */}
            {detectJobId && (
              <div className="rounded-lg border border-gray-200 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-console-bg border-b border-white/10">
                  <span className="text-[11px] font-semibold text-console-accent uppercase tracking-widest">
                    {t('addServer.detectTitle')}
                  </span>
                  {!detectDone && <Spinner size={12} className="text-console-accent" />}
                  {detectDone && <CheckCircle size={12} className="text-green-400" />}
                </div>
                <div className="bg-console-bg max-h-56 overflow-y-auto p-3 font-mono text-[11px] space-y-0.5">
                  {detectLogs.length === 0 && (
                    <span className="text-console-muted">{t('jobs.connecting')}</span>
                  )}
                  {detectLogs.map((line, i) => (
                    <div key={i} className={logLineClass(line)}>{line}</div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}
          </div>
        )}

        {result && !result.success && (
          <div className="mt-4 flex items-start gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
            <XCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-red-700">{t('addServer.failTitle')}</p>
              <p className="text-[12px] text-red-600 mt-0.5">{result.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Zone 2: SSH Setup (console theme) ── */}
      <div className="bg-console-bg rounded-xl p-6 max-w-2xl">
        <div className="flex items-center gap-2 mb-4">
          <Terminal size={14} className="text-console-accent" />
          <h3 className="text-[13px] font-semibold text-console-text">{t('addServer.helper.title')}</h3>
        </div>
        <p className="text-[12px] text-console-muted mb-5 leading-relaxed">
          {t('addServer.helper.description')}
        </p>

        {/* Option 1 — Online: curl | sudo bash */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Globe size={12} className="text-console-accent" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-console-accent">
              {t('addServer.helper.onlineTitle')}
            </p>
          </div>

          <div className="mb-3">
            <label className="block text-[10px] font-medium text-console-muted mb-1.5">
              {t('addServer.helper.platformUrl')}
            </label>
            <input
              value={platformUrl}
              onChange={(e) => setPlatformUrl(e.target.value)}
              placeholder="http://192.168.1.5"
              className="w-full px-3 py-2 text-[12px] font-mono bg-console-surface border border-white/10 rounded-lg outline-none text-console-text placeholder:text-console-muted focus:border-white/30 transition-colors"
            />
            <p className="text-[10px] text-console-muted mt-1">
              {t('addServer.helper.platformUrlHint')}
            </p>
          </div>

          <p className="text-[10px] text-console-muted mb-1.5">{t('addServer.helper.runOnTarget')}</p>
          <div className="bg-console-surface rounded-lg p-3 flex items-start justify-between gap-3">
            <pre className="text-[12px] font-mono text-console-text whitespace-pre-wrap flex-1 leading-relaxed">{curlCmd}</pre>
            <CopyButton
              text={curlCmd}
              className="p-1 rounded hover:bg-white/10 text-console-muted hover:text-console-text flex-shrink-0"
              onResult={(ok) => toast(ok ? t('common.copied') : t('common.copyFailed'), ok ? 'success' : 'error')}
            />
          </div>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 border-t border-white/10" />
          <span className="text-[10px] font-semibold text-console-muted uppercase">{t('addServer.helper.or')}</span>
          <div className="flex-1 border-t border-white/10" />
        </div>

        {/* Option 2 — Airgap: download + transfer */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <HardDriveDownload size={12} className="text-console-accent" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-console-accent">
              {t('addServer.helper.airgapTitle')}
            </p>
          </div>

          <div className="flex items-start gap-4 mb-3">
            <div className="flex-shrink-0">
              <button
                onClick={async () => {
                  try { await downloadSetupScript() }
                  catch (err) { toast(err.message, 'error') }
                }}
                className="flex items-center gap-2 px-4 py-2 bg-console-accent/20 hover:bg-console-accent/30 border border-console-accent/40 text-console-accent rounded-lg text-[12px] font-semibold transition-colors"
              >
                <Download size={13} />
                {t('addServer.helper.downloadBtn')}
              </button>
            </div>
            <p className="text-[10px] text-console-muted pt-1.5 leading-relaxed">
              {t('addServer.helper.airgapSteps')}
            </p>
          </div>

          <p className="text-[10px] text-console-muted mb-1.5">{t('addServer.helper.thenRun')}</p>
          <div className="bg-console-surface rounded-lg p-3 flex items-center justify-between gap-3">
            <pre className="text-[12px] font-mono text-console-text">{airgapCmd}</pre>
            <CopyButton
              text={airgapCmd}
              className="p-1 rounded hover:bg-white/10 text-console-muted hover:text-console-text flex-shrink-0"
              onResult={(ok) => toast(ok ? t('common.copied') : t('common.copyFailed'), ok ? 'success' : 'error')}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
