import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, Lock, RefreshCw, Search, X } from 'lucide-react'
import { getAuditLog, getAuditFacets, getUserRole } from '../lib/api.js'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import { utcDate } from '../lib/time.js'

const PAGE_SIZE = 100

const FORMAT_VARIANT = { csv: 'success', json: 'info', pdf: 'danger' }

function fmtWhen(iso) {
  const d = utcDate(iso)
  return d ? d.toLocaleString() : '—'
}

function Who({ entry }) {
  const name = entry.user_name || entry.api_key_name || '—'
  const role = entry.user_role
  return (
    <div className="min-w-0">
      <div className="text-gray-800 font-medium truncate">{name}</div>
      {role && <div className="text-[10px] text-gray-400 uppercase tracking-wide">{role}</div>}
    </div>
  )
}

function detailText(entry, t) {
  const d = entry.detail
  const parts = []
  if (d && typeof d === 'object') {
    if (typeof d.count === 'number') parts.push(t('audit.itemsExported', { count: d.count }))
    if (d.filename) parts.push(d.filename)
  }
  if (!parts.length && entry.path) parts.push(entry.path)
  return parts.join(' · ')
}

export default function AuditLogPage() {
  const t = useT()
  const isAdmin = getUserRole() === 'admin'

  const [exportsOnly, setExportsOnly] = useState(true)
  const [user, setUser] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [q, setQ] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const [facets, setFacets] = useState({ users: [], resource_types: [] })
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Debounce the free-text search so we don't refetch on every keystroke.
  const [qDebounced, setQDebounced] = useState('')
  useEffect(() => {
    const id = setTimeout(() => setQDebounced(q), 300)
    return () => clearTimeout(id)
  }, [q])

  const filters = useMemo(() => ({
    action: exportsOnly ? 'export' : undefined,
    user: user || undefined,
    resource_type: resourceType || undefined,
    q: qDebounced || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }), [exportsOnly, user, resourceType, qDebounced, dateFrom, dateTo])

  const load = useCallback(async (nextOffset = 0) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getAuditLog({ ...filters, limit: PAGE_SIZE, offset: nextOffset })
      setTotal(res.total || 0)
      setOffset(nextOffset)
      setItems((prev) => (nextOffset === 0 ? res.items : [...prev, ...res.items]))
    } catch (err) {
      setError(err.message || t('audit.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [filters, t])

  // Reload from the top whenever a filter changes.
  useEffect(() => { if (isAdmin) load(0) }, [load, isAdmin])

  useEffect(() => {
    if (!isAdmin) return
    getAuditFacets().then(setFacets).catch(() => {})
  }, [isAdmin])

  function clearFilters() {
    setExportsOnly(true); setUser(''); setResourceType('')
    setQ(''); setQDebounced(''); setDateFrom(''); setDateTo('')
  }

  const hasFilters = !exportsOnly || user || resourceType || q || dateFrom || dateTo

  if (!isAdmin) {
    // The VIEW is always reachable; the DATA is access-controlled. Show the page
    // frame with a clear restricted-access notice rather than a dead end.
    return (
      <div className="p-6 space-y-4">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
            <Download size={17} className="text-gray-400" /> {t('audit.title')}
          </h2>
          <p className="text-[13px] text-gray-500 mt-0.5">{t('audit.subtitle')}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center">
          <Lock size={22} className="text-gray-300 mx-auto mb-2" />
          <div className="text-[13px] font-medium text-gray-700">{t('audit.adminOnly')}</div>
          <div className="text-[11px] text-gray-400 mt-1">{t('topbar.restricted')}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
            <Download size={17} className="text-gray-400" /> {t('audit.title')}
          </h2>
          <p className="text-[13px] text-gray-500 mt-0.5">{t('audit.subtitle')}</p>
        </div>
        <button
          onClick={() => load(0)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-gray-600 text-[12px] font-medium hover:bg-gray-50"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> {t('audit.refresh')}
        </button>
      </div>

      {/* ── Filter bar ── */}
      <div className="bg-white rounded-xl border border-gray-100 p-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">{t('audit.filterAction')}</label>
          <select
            value={exportsOnly ? 'export' : 'all'}
            onChange={(e) => setExportsOnly(e.target.value === 'export')}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand bg-white"
          >
            <option value="export">{t('audit.exportsOnly')}</option>
            <option value="all">{t('audit.allActivity')}</option>
          </select>
        </div>

        <div>
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">{t('audit.filterUser')}</label>
          <select
            value={user}
            onChange={(e) => setUser(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand bg-white min-w-[140px]"
          >
            <option value="">{t('audit.allUsers')}</option>
            {facets.users.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">{t('audit.filterType')}</label>
          <select
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand bg-white min-w-[120px]"
          >
            <option value="">{t('audit.allTypes')}</option>
            {facets.resource_types.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">{t('audit.from')}</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand bg-white" />
        </div>
        <div>
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">{t('audit.to')}</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand bg-white" />
        </div>

        <div className="flex-1 min-w-[180px]">
          <label className="block text-[10px] font-medium text-gray-500 mb-1 uppercase tracking-wide">&nbsp;</label>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-300" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('audit.search')}
              className="w-full border border-gray-200 rounded-lg pl-8 pr-2.5 py-1.5 text-[12px] outline-none focus:border-brand"
            />
          </div>
        </div>

        {hasFilters && (
          <button onClick={clearFilters}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[12px] text-gray-500 hover:text-gray-800">
            <X size={13} /> {t('audit.clear')}
          </button>
        )}
      </div>

      {error && <div className="text-[13px] text-red-600">{error}</div>}

      {/* ── Table ── */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100">
                <th className="px-4 py-2.5 font-medium">{t('audit.colWhen')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colWho')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colAction')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colResource')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colFormat')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colDetail')}</th>
                <th className="px-4 py-2.5 font-medium">{t('audit.colIp')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50/60">
                  <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">{fmtWhen(e.ts)}</td>
                  <td className="px-4 py-2.5"><Who entry={e} /></td>
                  <td className="px-4 py-2.5">
                    {e.action === 'export'
                      ? <span className={badge('admin')}>{t('audit.actionExport')}</span>
                      : <span className="text-gray-500">{e.method}</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="text-gray-800 truncate max-w-[240px]">{e.resource_name || e.path || '—'}</div>
                    {e.resource_type && <div className="text-[10px] text-gray-400">{e.resource_type}</div>}
                  </td>
                  <td className="px-4 py-2.5">
                    {e.format
                      ? <span className={badge(FORMAT_VARIANT[e.format] || 'gray')}>{e.format.toUpperCase()}</span>
                      : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 truncate max-w-[220px]">{detailText(e, t)}</td>
                  <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">{e.ip || '—'}</td>
                </tr>
              ))}
              {!items.length && !loading && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">{t('audit.empty')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between text-[12px] text-gray-400">
        <span>{t('audit.showing', { count: items.length, total })}</span>
        {items.length < total && (
          <button
            onClick={() => load(offset + PAGE_SIZE)}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            {t('audit.loadMore')}
          </button>
        )}
      </div>
    </div>
  )
}
