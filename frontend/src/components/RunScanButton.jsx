import { useState } from 'react'
import { Play, ChevronDown } from 'lucide-react'

// Profiles the scan can be labelled with. The first (null) is the default that
// the main button runs when clicked without opening the menu.
export const PROFILE_OPTIONS = [
  { id: null,                  labelKey: 'compliance.allProfiles' },
  { id: 'cis-benchmark',       labelKey: 'compliance.cisBenchmark' },
  { id: 'sabc-linux-baseline', labelKey: 'compliance.internalRef' },
]

// Split button: clicking the main body runs the default scan; the chevron opens
// a menu to run a scan for a specific profile. Replaces the old profile-selector
// button group — the choice now lives inside the Run Scan control itself.
export default function RunScanButton({
  onRun, running = false, disabled = false, t,
  label, runningLabel, size = 'md',
}) {
  const [open, setOpen] = useState(false)
  const pad = size === 'sm' ? 'px-3.5 py-1.5 text-[12px]' : 'px-4 py-2 text-[13px]'
  const chev = size === 'sm' ? 'px-1.5 py-1.5' : 'px-2 py-2'

  function run(profileId) {
    setOpen(false)
    onRun(profileId)
  }

  return (
    <div className="relative inline-flex">
      <div className="inline-flex rounded-lg overflow-hidden shadow-sm">
        <button
          onClick={() => run(null)}
          disabled={disabled || running}
          className={`inline-flex items-center gap-1.5 ${pad} bg-brand text-white font-medium hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <Play size={size === 'sm' ? 13 : 14} className={running ? 'animate-pulse' : ''} />
          {running ? (runningLabel || t('compliance.scanning')) : (label || t('compliance.runScan'))}
        </button>
        <button
          onClick={() => setOpen((o) => !o)}
          disabled={disabled || running}
          aria-label={t('compliance.chooseProfile')}
          title={t('compliance.chooseProfile')}
          className={`${chev} bg-brand text-white border-l border-white/25 hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <ChevronDown size={13} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-lg shadow-lg z-20 w-52 py-1 text-[12px]">
            <div className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
              {t('compliance.chooseProfile')}
            </div>
            {PROFILE_OPTIONS.map((p) => (
              <button
                key={String(p.id)}
                onClick={() => run(p.id)}
                className="w-full text-left px-3.5 py-2 hover:bg-gray-50 text-gray-700"
              >
                {t(p.labelKey)}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
