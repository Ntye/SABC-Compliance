import { useT } from '../context/LangContext.jsx'

export default function OverviewPage() {
  const t = useT()
  return (
    <div className="p-6">
      <h2 className="text-[18px] font-semibold text-gray-900 mb-2">{t('overview.title')}</h2>
      <p className="text-[13px] text-gray-500">{t('overview.comingSoon')}</p>
    </div>
  )
}
