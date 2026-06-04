import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/api.js'
import Spinner from '../components/common/Spinner.jsx'
import { useT } from '../context/LangContext.jsx'
import sabcLogo from '../assets/sabc-logo.svg'

export default function LoginPage() {
  const navigate = useNavigate()
  const t = useT()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username || !password) { setError(t('login.errorRequired')); return }
    setLoading(true); setError('')
    try {
      await login(username, password)
      navigate('/overview', { replace: true })
    } catch (err) {
      setError(err.message || t('login.errorFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-page flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <img src={sabcLogo} alt="SABC — Boissons du Cameroun" className="h-16 mx-auto" />
          <div className="text-[13px] text-gray-500 mt-2">{t('nav.platform')}</div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h2 className="text-[16px] font-semibold text-gray-900 mb-6">{t('login.title')}</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] font-medium text-gray-600 mb-1.5">
                {t('login.username')}
              </label>
              <input
                type="text" autoComplete="username"
                value={username} onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                placeholder="admin" disabled={loading}
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-gray-600 mb-1.5">
                {t('login.password')}
              </label>
              <input
                type="password" autoComplete="current-password"
                value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all"
                placeholder="••••••••" disabled={loading}
              />
            </div>

            {error && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-[12px] text-red-600">{error}</p>
              </div>
            )}

            <button
              type="submit" disabled={loading}
              className="w-full py-2.5 bg-brand text-white text-[13px] font-medium rounded-lg hover:bg-brand/90 active:scale-[0.99] transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading && <Spinner size={14} />}
              {loading ? t('login.signingIn') : t('login.signIn')}
            </button>
          </form>
        </div>

        <p className="text-center text-[11px] text-gray-400 mt-6">{t('login.tagline')}</p>
      </div>
    </div>
  )
}
