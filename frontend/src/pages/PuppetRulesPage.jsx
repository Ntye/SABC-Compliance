import { useT } from '../context/LangContext.jsx'

export default function PuppetRulesPage() {
  const t = useT()
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-2">{t('rules.title')}</h2>
      <p className="text-[13px] text-gray-500">{t('rules.comingSoon')}</p>
    </div>
  )
}
