import { useState } from 'react'
import { ShieldCheck, Upload, Lock, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { getTlsCertificate, uploadTlsCertificate } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import Spinner from '../components/common/Spinner.jsx'

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function CertSummary({ info }) {
  if (!info || !info.installed) {
    return <p className="text-[13px] text-gray-500">No certificate is currently installed.</p>
  }
  if (info.parse_error) {
    return (
      <div className="flex items-start gap-2 text-[12px] text-amber-700">
        <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
        <span>A certificate file exists but could not be parsed: {info.parse_error}</span>
      </div>
    )
  }
  const rows = [
    ['Subject (CN)', info.subject_cn || '—'],
    ['Issuer (CN)', info.issuer_cn || '—'],
    ['Type', info.self_signed ? 'Self-signed (default)' : 'CA-signed'],
    ['Valid from', fmtDate(info.not_before)],
    ['Expires', fmtDate(info.not_after)],
    ['SANs', (info.sans && info.sans.length) ? info.sans.join(', ') : '—'],
  ]
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-1">
        {info.self_signed ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle size={11} /> Self-signed — browsers show a warning
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium rounded-full bg-green-50 text-green-700 border border-green-200">
            <CheckCircle2 size={11} /> CA-signed — trusted
          </span>
        )}
        {info.expired ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium rounded-full bg-red-50 text-red-700 border border-red-200">
            Expired
          </span>
        ) : typeof info.days_until_expiry === 'number' && info.days_until_expiry <= 30 ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            Expires in {info.days_until_expiry} day{info.days_until_expiry === 1 ? '' : 's'}
          </span>
        ) : null}
      </div>
      <dl className="grid grid-cols-[140px_1fr] gap-x-3 gap-y-1.5 text-[12px]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-gray-400 font-medium">{k}</dt>
            <dd className="text-gray-700 break-all">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export default function TlsCertificatePage() {
  const toast = useToast()
  const { data: info, loading, error, refetch } = useApi(getTlsCertificate)

  const [certFile, setCertFile] = useState(null)
  const [keyFile, setKeyFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  async function handleUpload(e) {
    e.preventDefault()
    if (!certFile || !keyFile) {
      toast('Select both a certificate and a private key file.', 'error')
      return
    }
    setUploading(true)
    try {
      await uploadTlsCertificate(certFile, keyFile)
      setCertFile(null)
      setKeyFile(null)
      // reset the native file inputs
      document.getElementById('tls-cert-input').value = ''
      document.getElementById('tls-key-input').value = ''
      refetch()
      toast('Certificate installed — the platform reloads HTTPS within a few seconds.', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck size={20} className="text-brand" />
        <h2 className="text-[18px] font-semibold text-gray-900">TLS Certificate</h2>
      </div>
      <p className="text-[13px] text-gray-500 mb-6 max-w-xl">
        Install a CA-signed certificate so the platform serves HTTPS without browser warnings.
        The new certificate takes effect automatically — no restart, no server access required.
      </p>

      {/* Current certificate */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-6">
        <h3 className="text-[13px] font-semibold text-gray-700 mb-4">Current certificate</h3>
        {loading && <div className="h-20 bg-gray-100 animate-pulse rounded" />}
        {error && <p className="text-[12px] text-red-600">{error}</p>}
        {!loading && !error && <CertSummary info={info} />}
      </div>

      {/* Upload form */}
      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h3 className="text-[13px] font-semibold text-gray-700 mb-1">Install a new certificate</h3>
        <p className="text-[12px] text-gray-500 mb-4">
          Upload the PEM certificate and its private key. If your CA provided intermediate
          certificates, concatenate them into the certificate file (server cert first, then the chain).
          The key must be unencrypted (no passphrase).
        </p>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">
              Certificate (PEM — .crt / .pem)
            </label>
            <input
              id="tls-cert-input"
              type="file"
              accept=".crt,.pem,.cer,application/x-pem-file,application/pkix-cert"
              onChange={(e) => setCertFile(e.target.files?.[0] || null)}
              className="block w-full text-[12px] text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-[12px] file:font-medium file:bg-brand/10 file:text-brand hover:file:bg-brand/20 cursor-pointer"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-gray-500 mb-1">
              Private key (PEM — .key, unencrypted)
            </label>
            <input
              id="tls-key-input"
              type="file"
              accept=".key,.pem,application/x-pem-file"
              onChange={(e) => setKeyFile(e.target.files?.[0] || null)}
              className="block w-full text-[12px] text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-[12px] file:font-medium file:bg-brand/10 file:text-brand hover:file:bg-brand/20 cursor-pointer"
            />
          </div>

          <div className="flex items-start gap-2 text-[11px] text-gray-500 bg-gray-50 rounded-lg p-3">
            <Lock size={13} className="mt-0.5 flex-shrink-0 text-gray-400" />
            <span>
              The pair is validated before anything is written — the key must match the certificate
              and the certificate must not be expired. A rejected upload never affects the running site.
            </span>
          </div>

          <button
            type="submit"
            disabled={uploading || !certFile || !keyFile}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand text-white text-[13px] font-medium rounded-lg hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? <Spinner size={13} /> : <Upload size={13} />}
            {uploading ? 'Installing…' : 'Install certificate'}
          </button>
        </form>
      </div>
    </div>
  )
}
