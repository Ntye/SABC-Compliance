import { Moon, Palette, RotateCcw, Sun, X } from 'lucide-react'
import { useTheme, THEMES } from '../../context/ThemeContext.jsx'
import { useLang } from '../../context/LangContext.jsx'

const THEME_KEYS = ['sabc', 'ocean', 'forest', 'midnight', 'slate', 'sunset']

// Swatch colours shown on the grid cards (always fixed, not CSS-var driven,
// so the preview makes sense regardless of current active theme)
const SWATCH = {
  sabc:     { primary: '#C0281F', secondary: '#D97706' },
  ocean:    { primary: '#1D4ED8', secondary: '#0891B2' },
  forest:   { primary: '#059669', secondary: '#16A34A' },
  midnight: { primary: '#4F46E5', secondary: '#7C3AED' },
  slate:    { primary: '#334155', secondary: '#0EA5E9' },
  sunset:   { primary: '#EA580C', secondary: '#DB2777' },
}

// Small color-picker swatch with invisible native input overlay
function ColorSwatch({ value, onChange }) {
  return (
    <div className="relative w-9 h-9 rounded-lg border-2 border-[var(--border-strong)] cursor-pointer overflow-hidden flex-shrink-0"
         style={{ backgroundColor: value }}>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
    </div>
  )
}

export default function ThemePanel({ onClose }) {
  const { theme, mode, customPrimary, customSecondary, setTheme, setMode, setCustomColors, resetToDefaults } = useTheme()
  const { lang, t, setLang } = useLang()

  const preset = THEMES[theme]?.[mode] ?? THEMES.sabc.light
  const effectivePrimary   = customPrimary   || preset.brand
  const effectiveSecondary = customSecondary || preset.accent

  return (
    /* overlay */
    <div className="fixed inset-0 z-[60] flex items-start justify-end" onClick={onClose}>
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/25" />

      {/* panel */}
      <div
        className="relative h-full w-80 flex flex-col shadow-2xl overflow-hidden"
        style={{ backgroundColor: 'var(--bg-card)', borderLeft: '1px solid var(--border-strong)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 flex-shrink-0"
             style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg-card)' }}>
          <div className="flex items-center gap-2">
            <Palette size={15} style={{ color: 'rgb(var(--brand-rgb))' }} />
            <h2 className="text-[14px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              {t('settings.title')}
            </h2>
          </div>
          <button onClick={onClose}
                  className="p-1.5 rounded-md transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  onMouseEnter={e => e.currentTarget.style.backgroundColor='var(--bg-subtle)'}
                  onMouseLeave={e => e.currentTarget.style.backgroundColor='transparent'}>
            <X size={15} />
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-7">

          {/* Language */}
          <section>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3"
               style={{ color: 'var(--text-muted)' }}>{t('settings.language')}</p>
            <div className="flex gap-2">
              {[{ id: 'en', label: 'English' }, { id: 'fr', label: 'Français' }].map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => setLang(id)}
                  className="px-4 py-1.5 rounded-lg text-[12px] font-semibold transition-all"
                  style={lang === id
                    ? { backgroundColor: 'rgb(var(--brand-rgb))', color: '#fff' }
                    : { backgroundColor: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}
                >
                  {label}
                </button>
              ))}
            </div>
          </section>

          {/* Color mode */}
          <section>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3"
               style={{ color: 'var(--text-muted)' }}>{t('settings.colorMode')}</p>
            <div className="flex gap-2">
              {[
                { id: 'light', icon: Sun,  label: t('settings.light') },
                { id: 'dark',  icon: Moon, label: t('settings.dark')  },
              ].map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  onClick={() => setMode(id)}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[12px] font-semibold transition-all"
                  style={mode === id
                    ? { backgroundColor: 'rgb(var(--brand-rgb))', color: '#fff' }
                    : { backgroundColor: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}
                >
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>
          </section>

          {/* Theme grid */}
          <section>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3"
               style={{ color: 'var(--text-muted)' }}>{t('settings.theme')}</p>
            <div className="grid grid-cols-3 gap-2">
              {THEME_KEYS.map((name) => {
                const sw = SWATCH[name]
                const isActive = theme === name && !customPrimary && !customSecondary
                return (
                  <button
                    key={name}
                    onClick={() => { setTheme(name); setCustomColors({ primary: '', secondary: '' }) }}
                    className="flex flex-col items-center gap-2 p-3 rounded-xl transition-all"
                    style={{
                      border: `2px solid ${isActive ? 'rgb(var(--brand-rgb))' : 'transparent'}`,
                      backgroundColor: isActive ? 'rgba(var(--brand-rgb),.06)' : 'var(--bg-subtle)',
                    }}
                  >
                    {/* dual-tone swatch circle */}
                    <div className="w-8 h-8 rounded-full shadow-sm overflow-hidden flex">
                      <div className="flex-1" style={{ backgroundColor: sw.primary }} />
                      <div className="flex-1" style={{ backgroundColor: sw.secondary }} />
                    </div>
                    <span className="text-[10px] font-medium" style={{ color: 'var(--text-secondary)' }}>
                      {t(`settings.themes.${name}`)}
                    </span>
                  </button>
                )
              })}
            </div>
          </section>

          {/* Custom colors */}
          <section>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-4"
               style={{ color: 'var(--text-muted)' }}>{t('settings.customColors')}</p>

            {/* Primary */}
            <div className="flex items-start gap-3 mb-5">
              <ColorSwatch
                value={effectivePrimary}
                onChange={(v) => setCustomColors({ primary: v, secondary: customSecondary })}
              />
              <div className="min-w-0">
                <p className="text-[12px] font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>
                  {t('settings.primaryColor')}
                </p>
                <p className="text-[10px] leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {t('settings.primaryHint')}
                </p>
                <p className="text-[10px] font-mono mt-1" style={{ color: 'rgb(var(--brand-rgb))' }}>
                  {effectivePrimary}
                </p>
              </div>
            </div>

            {/* Secondary */}
            <div className="flex items-start gap-3">
              <ColorSwatch
                value={effectiveSecondary}
                onChange={(v) => setCustomColors({ primary: customPrimary, secondary: v })}
              />
              <div className="min-w-0">
                <p className="text-[12px] font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>
                  {t('settings.secondaryColor')}
                </p>
                <p className="text-[10px] leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                  {t('settings.secondaryHint')}
                </p>
                <p className="text-[10px] font-mono mt-1" style={{ color: 'rgb(var(--accent-rgb))' }}>
                  {effectiveSecondary}
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* ── Footer ── */}
        <div className="px-5 py-4 flex-shrink-0 space-y-3"
             style={{ borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-subtle)' }}>
          <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {t('settings.previewNote')}
          </p>
          <button
            onClick={resetToDefaults}
            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-[12px] font-medium transition-colors"
            style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-secondary)', border: '1px solid var(--border-strong)' }}
            onMouseEnter={e => e.currentTarget.style.backgroundColor='var(--bg-card-hover)'}
            onMouseLeave={e => e.currentTarget.style.backgroundColor='var(--bg-card)'}
          >
            <RotateCcw size={12} /> {t('settings.reset')}
          </button>
        </div>
      </div>
    </div>
  )
}
