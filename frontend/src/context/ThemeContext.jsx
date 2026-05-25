import { createContext, useContext, useEffect, useState } from 'react'

// ── helpers ───────────────────────────────────────────────────────────────────

function hexToRgbTriplet(hex) {
  const h = hex.replace('#', '')
  return `${parseInt(h.slice(0,2),16)} ${parseInt(h.slice(2,4),16)} ${parseInt(h.slice(4,6),16)}`
}

function mixWithWhite(hex, weight = 0.12) {
  const h = hex.replace('#', '')
  const mix = (c) => Math.round(parseInt(c,16) * weight + 255 * (1 - weight))
  const r = mix(h.slice(0,2)), g = mix(h.slice(2,4)), b = mix(h.slice(4,6))
  return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`
}

function mixWithBlack(hex, weight = 0.20) {
  const h = hex.replace('#', '')
  const mix = (c) => Math.round(parseInt(c,16) * weight)
  const r = mix(h.slice(0,2)), g = mix(h.slice(2,4)), b = mix(h.slice(4,6))
  return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`
}

// ── preset data ───────────────────────────────────────────────────────────────

export const THEMES = {
  bdc:      { light: { brand: '#C0281F', accent: '#D97706' }, dark: { brand: '#E8453A', accent: '#F59E0B' } },
  ocean:    { light: { brand: '#1D4ED8', accent: '#0891B2' }, dark: { brand: '#3B82F6', accent: '#22D3EE' } },
  forest:   { light: { brand: '#059669', accent: '#16A34A' }, dark: { brand: '#10B981', accent: '#22C55E' } },
  midnight: { light: { brand: '#4F46E5', accent: '#7C3AED' }, dark: { brand: '#6366F1', accent: '#A78BFA' } },
  slate:    { light: { brand: '#334155', accent: '#0EA5E9' }, dark: { brand: '#94A3B8', accent: '#38BDF8' } },
  sunset:   { light: { brand: '#EA580C', accent: '#DB2777' }, dark: { brand: '#F97316', accent: '#EC4899' } },
}

const LIGHT_STRUCTURAL = {
  bgPage: '#F8F6F3', bgCard: '#FFFFFF', bgCardHover: '#F9FAFB',
  bgInput: '#FFFFFF', bgSubtle: '#F9FAFB',
  textPrimary: '#111827', textSecondary: '#4B5563', textMuted: '#9CA3AF',
  border: '#F3F4F6', borderStrong: '#E5E7EB', sidebarBg: '#1C1C1E',
}

const DARK_STRUCTURAL = {
  bgPage: '#0F0F0F', bgCard: '#1A1A1A', bgCardHover: '#262626',
  bgInput: '#1E1E1E', bgSubtle: '#222222',
  textPrimary: '#F5F5F5', textSecondary: '#C9C9C9', textMuted: '#6B7280',
  border: '#2A2A2A', borderStrong: '#333333', sidebarBg: '#0D0D0F',
}

// ── CSS variable application ───────────────────────────────────────────────────

function applyVars(theme, mode, customPrimary, customSecondary) {
  const root = document.documentElement
  root.setAttribute('data-theme', theme)
  root.setAttribute('data-mode', mode)

  const structural = mode === 'dark' ? DARK_STRUCTURAL : LIGHT_STRUCTURAL
  root.style.setProperty('--bg-page',       structural.bgPage)
  root.style.setProperty('--bg-card',       structural.bgCard)
  root.style.setProperty('--bg-card-hover', structural.bgCardHover)
  root.style.setProperty('--bg-input',      structural.bgInput)
  root.style.setProperty('--bg-subtle',     structural.bgSubtle)
  root.style.setProperty('--text-primary',  structural.textPrimary)
  root.style.setProperty('--text-secondary',structural.textSecondary)
  root.style.setProperty('--text-muted',    structural.textMuted)
  root.style.setProperty('--border',        structural.border)
  root.style.setProperty('--border-strong', structural.borderStrong)
  root.style.setProperty('--sidebar-bg',    structural.sidebarBg)

  const preset = THEMES[theme]?.[mode] ?? THEMES.bdc.light
  const brand  = customPrimary  || preset.brand
  const accent = customSecondary || preset.accent

  root.style.setProperty('--brand-rgb',   hexToRgbTriplet(brand))
  root.style.setProperty('--accent-rgb',  hexToRgbTriplet(accent))
  root.style.setProperty('--brand-light', mode === 'dark' ? mixWithBlack(brand, 0.25) : mixWithWhite(brand))
  root.style.setProperty('--accent-light',mode === 'dark' ? mixWithBlack(accent, 0.25) : mixWithWhite(accent))
}

// ── context ───────────────────────────────────────────────────────────────────

const ThemeContext = createContext()

export function ThemeProvider({ children }) {
  const [theme,         setThemeState]   = useState(() => localStorage.getItem('bdc_theme')          || 'bdc')
  const [mode,          setModeState]    = useState(() => localStorage.getItem('bdc_mode')           || 'light')
  const [customPrimary, setCustomPrimary]= useState(() => localStorage.getItem('bdc_custom_primary') || '')
  const [customSecondary,setCustomSecondary]=useState(()=>localStorage.getItem('bdc_custom_secondary')||'')

  function setTheme(t) { setThemeState(t); localStorage.setItem('bdc_theme', t) }
  function setMode(m)  { setModeState(m);  localStorage.setItem('bdc_mode',  m) }

  function setCustomColors({ primary, secondary }) {
    const p = primary  ?? customPrimary
    const s = secondary ?? customSecondary
    setCustomPrimary(p);  p ? localStorage.setItem('bdc_custom_primary', p)   : localStorage.removeItem('bdc_custom_primary')
    setCustomSecondary(s);s ? localStorage.setItem('bdc_custom_secondary', s) : localStorage.removeItem('bdc_custom_secondary')
  }

  function resetToDefaults() {
    setThemeState('bdc'); setModeState('light')
    setCustomPrimary(''); setCustomSecondary('')
    ;['bdc_theme','bdc_mode','bdc_custom_primary','bdc_custom_secondary'].forEach(k => localStorage.removeItem(k))
  }

  useEffect(() => {
    applyVars(theme, mode, customPrimary, customSecondary)
  }, [theme, mode, customPrimary, customSecondary])

  return (
    <ThemeContext.Provider value={{ theme, mode, customPrimary, customSecondary, setTheme, setMode, setCustomColors, resetToDefaults }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
