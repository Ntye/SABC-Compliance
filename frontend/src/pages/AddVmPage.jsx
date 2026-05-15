import { useRef, useState } from 'react'
import { CheckCircle, Copy, Terminal, XCircle } from 'lucide-react'
import { registerNode } from '../lib/api.js'
import { useToast } from '../context/ToastContext.jsx'
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
  const [form, setForm] = useState(DEFAULT_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null) // { success: bool, node?, error? }
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
        tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
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

  const sshKey = form.ssh_key_path || './keys/ansible_id_rsa'
  const sshUser = form.ssh_user || 'ansible'
  const bUser = bootstrapUser || 'root'
  const sudoPrefix = bUser === 'root' ? '' : 'sudo '

  const setupCmd = `# 0. If you see "REMOTE HOST IDENTIFICATION HAS CHANGED", clear the cached entry first:
ssh-keygen -R ${form.ip || '<server-ip>'}

# 1. Create the ${sshUser} user (connect as ${bUser})
ssh -o StrictHostKeyChecking=no ${bUser}@${form.ip || '<server-ip>'} "
  ${sudoPrefix}useradd -m -s /bin/bash ${sshUser} 2>/dev/null || true
  ${sudoPrefix}mkdir -p /home/${sshUser}/.ssh
  ${sudoPrefix}chmod 700 /home/${sshUser}/.ssh
  ${sudoPrefix}chown ${sshUser}:${sshUser} /home/${sshUser}/.ssh
"

# 2. Install the PLATFORM key — run from backend/ directory
cat ${sshKey}.pub | ssh -o StrictHostKeyChecking=no ${bUser}@${form.ip || '<server-ip>'} "
  ${sudoPrefix}tee -a /home/${sshUser}/.ssh/authorized_keys
  ${sudoPrefix}chmod 600 /home/${sshUser}/.ssh/authorized_keys
  ${sudoPrefix}chown ${sshUser}:${sshUser} /home/${sshUser}/.ssh/authorized_keys
"

# 3. Grant passwordless sudo
ssh -o StrictHostKeyChecking=no ${bUser}@${form.ip || '<server-ip>'} "
  echo '${sshUser} ALL=(ALL) NOPASSWD:ALL' | ${sudoPrefix}tee /etc/sudoers.d/${sshUser}
  ${sudoPrefix}chmod 440 /etc/sudoers.d/${sshUser}
"`

  const verifyCmd = `ssh -i ${sshKey} \\
  -o StrictHostKeyChecking=no \\
  -o ConnectTimeout=5 \\
  ${sshUser}@${form.ip || '<server-ip>'} "echo OK && sudo id"`

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h2 className="text-[18px] font-semibold text-gray-900">Add VM</h2>

      {/* ── Zone 1: Registration form (light theme) ── */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 max-w-2xl">
        <h3 className="text-[14px] font-semibold text-gray-800 mb-5">Register a Linux Server</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Row: hostname + IP */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">
                Hostname <span className="text-red-500">*</span>
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
                IP Address <span className="text-red-500">*</span>
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
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">SSH Port</label>
              <input
                type="number"
                value={form.ssh_port}
                onChange={set('ssh_port')}
                placeholder="22"
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1.5">SSH User</label>
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
              SSH Key Path <span className="text-gray-400">(optional — uses platform default if blank)</span>
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
            <label className="block text-[11px] font-medium text-gray-500 mb-1.5">Description</label>
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
              Tags <span className="text-gray-400">(comma-separated)</span>
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
            {submitting ? 'Registering…' : 'Register server'}
          </button>
        </form>

        {/* Inline result */}
        {result && result.success && (
          <div className="mt-4 flex items-start gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-green-800">Node registered successfully</p>
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
              <p className="text-[13px] font-medium text-red-700">Registration failed</p>
              <p className="text-[12px] text-red-600 mt-0.5">{result.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Zone 2: SSH Setup Helper (console theme) ── */}
      <div className="bg-console-bg rounded-xl p-6 max-w-2xl">
        <div className="flex items-center gap-2 mb-4">
          <Terminal size={14} className="text-console-accent" />
          <h3 className="text-[13px] font-semibold text-console-text">SSH Setup Helper</h3>
        </div>
        <p className="text-[12px] text-console-muted mb-4 leading-relaxed">
          The platform connects to each server over SSH using the ansible user and key-based authentication.
          Run these commands from your <span className="font-mono text-console-text">backend/</span> directory before registering.
        </p>
        <div className="mb-5">
          <label className="block text-[10px] font-semibold uppercase tracking-widest text-console-muted mb-1.5">
            Your admin user on this server
          </label>
          <input
            value={bootstrapUser}
            onChange={(e) => setBootstrapUser(e.target.value)}
            placeholder="root / debian / ubuntu / ec2-user"
            className="w-full px-3 py-2 text-[12px] font-mono bg-console-surface border border-white/10 rounded-lg outline-none text-console-text placeholder:text-console-muted focus:border-white/30 transition-colors"
          />
          <p className="text-[10px] text-console-muted mt-1">
            The user you SSH into this server as today (must have sudo or be root). The commands below update automatically.
          </p>
        </div>
        <CodeBlock label="1 — Create user + authorize key" code={setupCmd} />
        <CodeBlock label="2 — Verify connection (run from this machine)" code={verifyCmd} />
        <p className="text-[11px] text-console-muted mt-2">
          The platform key is <span className="font-mono text-console-text">keys/ansible_id_rsa.pub</span> — never your personal <span className="font-mono text-console-text">~/.ssh</span> key.
          Step 2 pipes it through your admin session so the ansible user never needs a password.
        </p>
      </div>
    </div>
  )
}
