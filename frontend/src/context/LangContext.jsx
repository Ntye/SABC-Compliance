import { createContext, useContext, useState } from 'react'
import { translations } from '../i18n/translations.js'

function resolve(obj, path) {
  return path.split('.').reduce((acc, k) => acc?.[k], obj)
}

function interpolate(str, vars) {
  if (!vars || typeof str !== 'string') return str
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), String(v)),
    str,
  )
}

const LangContext = createContext()

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(
    () => localStorage.getItem('sabc_lang') || 'en',
  )

  function t(key, vars) {
    const str = resolve(translations[lang], key) ?? resolve(translations.en, key) ?? key
    return interpolate(str, vars)
  }

  function setLang(l) {
    setLangState(l)
    localStorage.setItem('sabc_lang', l)
  }

  return (
    <LangContext.Provider value={{ lang, t, setLang }}>
      {children}
    </LangContext.Provider>
  )
}

export const useLang = () => useContext(LangContext)
export const useT   = () => useContext(LangContext).t
