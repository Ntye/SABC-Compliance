import { useT } from '../context/LangContext.jsx'

export default function CompliancePage() {
  const t = useT()
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-2">{t('compliance.title')}</h2>
      <p className="text-[13px] text-gray-500">{t('compliance.comingSoon')}</p>
    </div>
  )
}
