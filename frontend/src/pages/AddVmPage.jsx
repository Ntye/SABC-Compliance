import { useState } from 'react'
import { CheckCircle, Copy, Download, Terminal, XCircle } from 'lucide-react'
import { downloadSetupScript, registerNode } from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  async function handleCopy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded hover:bg-white/10 text-console-muted hover:text-console-text transition-colors"
      title="Copy"
    >
      <Copy size={12} className={copied ? 'text-console-success' : ''} />
    </button>
  )
}

function CodeBlock({ code, label }) {
  return (
    <div className="mb-4">
      {label && <p className="text-[10px] font-semibold uppercase tracking-widest text-console-muted mb-1.5">{label}</p>}
      <div className="bg-console-surface rounded-lg p-3 flex items-start justify-between gap-3 group">
        <pre className="text-[12px] font-mono text-console-text whitespace-pre-wrap flex-1 leading-relaxed">{code}</pre>
        <CopyButton text={code} />
      </div>
    </div>
  )
}

const DEFAULT_FORM = {
  hostname: '',
  ip: '',
  ssh_port: '22',
  ssh_user: 'ansible',
  ssh_key_path: '',
  description: '',
  tags: '',
}

export default function AddVmPage() {
  const toast = useToast()
  const t = useT()
  const [form, setForm] = useState(DEFAULT_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [bootstrapUser, setBootstrapUser] = useState('root')

  function set(field) {
    return (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setResult(null)
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
      setTimeout(() => {
        setForm(DEFAULT_FORM)
        setResult(null)
      }, 2500)
    } catch (err) {
      setResult({ success: false, error: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const ip = form.ip || '<server-ip>'
  const bUser = bootstrapUser || 'root'
  const runCmd = `bash setup-node.sh ${ip} ${bUser}`

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h2 className="text-[18px] font-semibold text-gray-900">{t('addVm.title')}</h2>

      {/* ── Zone 1: Registration form ── */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 max-w-2xl">
        <h3 className="text-[14px] font-semibold text-gray-800 mb-5">{t('addVm.cardTitle')}</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Row: hostname + IP */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                {t('addVm.hostname')} <span className="text-red-500">{t('addVm.required')}</span>
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
                {t('addVm.ipAddress')} <span className="text-red-500">{t('addVm.required')}</span>
              </label>
              <input
                required
                value={form.ip}
                onChange={set('ip')}
                placeholder="192.168.1.10"
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
              />
            </div>
          </div>

          {/* Row: SSH port + SSH user */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addVm.sshPort')}</label>
              <input
                type="number"
                value={form.ssh_port}
                onChange={set('ssh_port')}
                placeholder="22"
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addVm.sshUser')}</label>
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
              {t('addVm.sshKeyPath')} <span className="text-gray-400">{t('addVm.sshKeyHint')}</span>
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
            <label className="block text-[11px] font-medium text-gray-500 mb-1.5">{t('addVm.description')}</label>
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
              {t('addVm.tags')} <span className="text-gray-400">{t('addVm.tagsHint')}</span>
            </label>
            <input
              value={form.tags}
              onChange={set('tags')}
              placeholder="production, web, dmz"
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className={`${btn(true)} w-full justify-center`}
          >
            {submitting && <Spinner size={14} />}
            {submitting ? t('addVm.registering') : t('addVm.register')}
          </button>
        </form>

        {/* Inline result */}
        {result && result.success && (
          <div className="mt-4 flex items-start gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-green-800">{t('addVm.successTitle')}</p>
              <p className="text-[12px] text-green-700 mt-0.5">
                {result.node.hostname} · {result.node.os_name || result.node.os_family || 'Unknown OS'} · {result.node.ip}
              </p>
            </div>
          </div>
        )}
        {result && !result.success && (
          <div className="mt-4 flex items-start gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg">
            <XCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-red-700">{t('addVm.failTitle')}</p>
              <p className="text-[12px] text-red-600 mt-0.5">{result.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Zone 2: SSH Setup Helper (console theme) ── */}
      <div className="bg-console-bg rounded-xl p-6 max-w-2xl">
        <div className="flex items-center gap-2 mb-4">
          <Terminal size={14} className="text-console-accent" />
          <h3 className="text-[13px] font-semibold text-console-text">{t('addVm.helper.title')}</h3>
        </div>
        <p className="text-[12px] text-console-muted mb-5 leading-relaxed">
          {t('addVm.helper.description')}
        </p>

        {/* Step 1 — download */}
        <div className="mb-5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-console-muted mb-2">
            {t('addVm.helper.step1')}
          </p>
          <button
            onClick={async () => {
              try { await downloadSetupScript() }
              catch (err) { toast(err.message, 'error') }
            }}
            className="flex items-center gap-2 px-4 py-2 bg-console-accent/20 hover:bg-console-accent/30 border border-console-accent/40 text-console-accent rounded-lg text-[12px] font-semibold transition-colors"
          >
            <Download size={13} />
            {t('addVm.helper.downloadBtn')}
          </button>
          <p className="text-[10px] text-console-muted mt-1.5">
            {t('addVm.helper.downloadHint')}
          </p>
        </div>

        {/* Step 2 — admin user input */}
        <div className="mb-5">
          <label className="block text-[10px] font-semibold uppercase tracking-widest text-console-muted mb-1.5">
            {t('addVm.helper.adminUser')}
          </label>
          <input
            value={bootstrapUser}
            onChange={(e) => setBootstrapUser(e.target.value)}
            placeholder="root / debian / ubuntu / ec2-user"
            className="w-full px-3 py-2 text-[12px] font-mono bg-console-surface border border-white/10 rounded-lg outline-none text-console-text placeholder:text-console-muted focus:border-white/30 transition-colors"
          />
          <p className="text-[10px] text-console-muted mt-1">
            {t('addVm.helper.adminUserHint')}
          </p>
        </div>

        {/* Step 3 — run command */}
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-console-muted mb-2">
            {t('addVm.helper.step2')}
          </p>
          <div className="bg-console-surface rounded-lg p-3 flex items-center justify-between gap-3">
            <pre className="text-[12px] font-mono text-console-text">{runCmd}</pre>
            <CopyButton text={runCmd} />
          </div>
          <p className="text-[11px] text-console-muted mt-2">
            {t('addVm.helper.runHint')}
          </p>
        </div>
      </div>
    </div>
  )
}
