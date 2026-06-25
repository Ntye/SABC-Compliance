import { useMemo, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronRight,
  Info, LifeBuoy, Search, Wrench,
} from 'lucide-react'
import { useLang, useT } from '../context/LangContext.jsx'
import { PLATFORMS, TROUBLESHOOTING } from '../data/troubleshooting.js'

const SEVERITY = {
  fixed:  { icon: CheckCircle2,  cls: 'text-green-600 bg-green-50 border-green-200' },
  action: { icon: Wrench,        cls: 'text-amber-600 bg-amber-50 border-amber-200' },
  info:   { icon: Info,          cls: 'text-blue-600 bg-blue-50 border-blue-200' },
}

function SeverityChip({ severity, t }) {
  const s = SEVERITY[severity] || SEVERITY.info
  const Icon = s.icon
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${s.cls}`}>
      <Icon size={11} />
      {t(`help.severity.${severity}`)}
    </span>
  )
}

function Entry({ entry, lang, t }) {
  const [open, setOpen] = useState(false)
  const pick = (field) => (field && (field[lang] ?? field.en)) || ''
  const steps = (entry.steps && (entry.steps[lang] ?? entry.steps.en)) || []

  return (
    <div className="bg-white rounded-xl border border-gray-100">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        {open ? <ChevronDown size={15} className="text-gray-400 flex-shrink-0" />
              : <ChevronRight size={15} className="text-gray-400 flex-shrink-0" />}
        <span className="flex-1 text-[13px] font-medium text-gray-900">{pick(entry.title)}</span>
        <SeverityChip severity={entry.severity} t={t} />
      </button>

      {open && (
        <div className="px-4 pb-4 pl-12 space-y-3 text-[12px] leading-relaxed">
          <div>
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{t('help.symptom')}</p>
            <p className="text-gray-700">{pick(entry.symptom)}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{t('help.cause')}</p>
            <p className="text-gray-700">{pick(entry.cause)}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{t('help.resolution')}</p>
            <ol className="list-decimal pl-4 space-y-1 text-gray-700">
              {steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          </div>
          {entry.code && (
            <pre className="bg-gray-900 text-gray-100 text-[11px] font-mono rounded-lg p-3 overflow-x-auto whitespace-pre">
              {entry.code}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export default function HelpPage() {
  const t = useT()
  const { lang } = useLang()
  const [query, setQuery] = useState('')
  const [platform, setPlatform] = useState('all')

  const q = query.trim().toLowerCase()
  const matches = useMemo(() => {
    return TROUBLESHOOTING.filter((e) => {
      if (platform !== 'all' && e.platform !== platform) return false
      if (!q) return true
      const hay = [e.title, e.symptom, e.cause]
        .map((f) => (f?.[lang] ?? f?.en ?? '')).join(' ').toLowerCase()
      const steps = (e.steps?.[lang] ?? e.steps?.en ?? []).join(' ').toLowerCase()
      return hay.includes(q) || steps.includes(q)
    })
  }, [q, platform, lang])

  const grouped = useMemo(() => {
    return PLATFORMS
      .map((p) => ({ ...p, entries: matches.filter((e) => e.platform === p.key) }))
      .filter((p) => p.entries.length > 0)
  }, [matches])

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center gap-2 mb-1">
        <LifeBuoy size={18} className="text-brand" />
        <h2 className="text-[18px] font-semibold text-gray-900">{t('help.title')}</h2>
      </div>
      <p className="text-[12px] text-gray-500 mb-5">{t('help.subtitle')}</p>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        <div className="flex items-center gap-2 flex-1 min-w-[220px] border border-gray-200 rounded-lg px-3 py-2">
          <Search size={14} className="text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('help.searchPlaceholder')}
            className="flex-1 text-[12px] outline-none bg-transparent text-gray-700 placeholder-gray-400"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setPlatform('all')}
            className={`px-2.5 py-1.5 rounded-md text-[12px] font-medium transition-all ${platform === 'all' ? 'bg-brand/15 text-brand' : 'text-gray-500 hover:bg-gray-100'}`}
          >
            {t('help.allPlatforms')}
          </button>
          {PLATFORMS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPlatform(p.key)}
              className={`px-2.5 py-1.5 rounded-md text-[12px] font-medium transition-all ${platform === p.key ? 'bg-brand/15 text-brand' : 'text-gray-500 hover:bg-gray-100'}`}
            >
              {p.label[lang] ?? p.label.en}
            </button>
          ))}
        </div>
      </div>

      {grouped.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <AlertTriangle size={28} className="mx-auto mb-2 opacity-40" />
          <p className="text-[13px]">{t('help.noResults')}</p>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map((p) => (
            <section key={p.key}>
              <h3 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                {p.label[lang] ?? p.label.en}
              </h3>
              <div className="space-y-2">
                {p.entries.map((e) => <Entry key={e.id} entry={e} lang={lang} t={t} />)}
              </div>
            </section>
          ))}
        </div>
      )}

      <p className="text-[11px] text-gray-400 mt-8 pt-4 border-t border-gray-100">
        {t('help.footer')}
      </p>
    </div>
  )
}
