import { useEffect, useState } from 'react'
import { FolderCog, Plus, Trash2, Save, UploadCloud, X, Lock, RotateCcw } from 'lucide-react'
import { getWatchConfig, updateWatchConfig, applyWatchConfig } from '../../lib/api.js'
import { useToast } from '../../context/ToastContext.jsx'
import { useT } from '../../context/LangContext.jsx'
import { badge } from '../../lib/tw.js'
import Spinner from '../common/Spinner.jsx'

const DEFAULT_PATHS = [
  '/etc/ssh/', '/etc/pam.d/', '/etc/sudoers', '/etc/sudoers.d/',
  '/etc/passwd', '/etc/group', '/etc/shadow',
]
const DEFAULT_HASH_ONLY = ['/etc/shadow']

// Panel to view and edit the folders/files the detection agents monitor. Lives
// in the detection plane; changes apply to new agents immediately and can be
// pushed to already-enrolled nodes with "Apply to nodes".
export default function WatchConfigPanel({ onClose }) {
  const t = useT()
  const toast = useToast()
  const [paths, setPaths] = useState([])
  const [hashOnly, setHashOnly] = useState([])
  const [isDefault, setIsDefault] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [applying, setApplying] = useState(false)
  const [newPath, setNewPath] = useState('')

  async function load() {
    setLoading(true)
    try {
      const cfg = await getWatchConfig()
      setPaths(cfg.paths || [])
      setHashOnly(cfg.hash_only || [])
      setIsDefault(!!cfg.is_default)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function addPath() {
    const p = newPath.trim()
    if (!p) return
    if (!p.startsWith('/')) { toast(t('watchConfig.mustBeAbsolute'), 'error'); return }
    if (paths.includes(p)) { setNewPath(''); return }
    setPaths((prev) => [...prev, p])
    setNewPath('')
  }

  function removePath(p) {
    setPaths((prev) => prev.filter((x) => x !== p))
    setHashOnly((prev) => prev.filter((x) => x !== p))
  }

  function toggleHashOnly(p) {
    setHashOnly((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]))
  }

  function resetDefaults() {
    setPaths([...DEFAULT_PATHS])
    setHashOnly([...DEFAULT_HASH_ONLY])
  }

  async function save() {
    if (paths.length === 0) { toast(t('watchConfig.needOne'), 'error'); return }
    setSaving(true)
    try {
      const cfg = await updateWatchConfig({ paths, hashOnly })
      setIsDefault(!!cfg.is_default)
      toast(t('watchConfig.saved'), 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function apply() {
    setApplying(true)
    try {
      const res = await applyWatchConfig()
      toast(t('watchConfig.applied', { n: res.launched ?? 0 }), 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 mb-5">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
        <h3 className="text-[13px] font-semibold text-gray-800 flex items-center gap-2">
          <FolderCog size={15} className="text-brand" />
          {t('watchConfig.title')}
          {isDefault && <span className={badge('gray')}>{t('watchConfig.defaultBadge')}</span>}
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={16} /></button>
      </div>

      <div className="p-5">
        <p className="text-[12px] text-gray-400 mb-4">{t('watchConfig.subtitle')}</p>

        {loading ? (
          <div className="h-24 bg-gray-100 animate-pulse rounded-lg" />
        ) : (
          <>
            {/* Path list */}
            <div className="border border-gray-100 rounded-lg divide-y divide-gray-50 mb-3">
              {paths.length === 0 ? (
                <p className="px-4 py-4 text-[12px] text-gray-400 text-center">{t('watchConfig.empty')}</p>
              ) : paths.map((p) => (
                <div key={p} className="flex items-center gap-3 px-4 py-2.5">
                  <code className="flex-1 text-[12px] font-mono text-gray-800">{p}</code>
                  <button
                    onClick={() => toggleHashOnly(p)}
                    title={t('watchConfig.hashOnlyHint')}
                    className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md border transition-colors ${
                      hashOnly.includes(p)
                        ? 'border-amber-300 bg-amber-50 text-amber-700'
                        : 'border-gray-200 text-gray-400 hover:text-gray-600'
                    }`}
                  >
                    <Lock size={11} /> {t('watchConfig.hashOnly')}
                  </button>
                  <button
                    onClick={() => removePath(p)}
                    className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>

            {/* Add path */}
            <div className="flex items-center gap-2 mb-4">
              <input
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addPath() } }}
                placeholder={t('watchConfig.addPlaceholder')}
                className="flex-1 px-3 py-2 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand"
              />
              <button onClick={addPath} className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-gray-200 text-gray-700 text-[12px] font-medium hover:bg-gray-50">
                <Plus size={13} /> {t('watchConfig.add')}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button onClick={save} disabled={saving} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-[13px] font-medium hover:bg-brand/90 disabled:opacity-50">
                {saving ? <Spinner size={12} /> : <Save size={13} />}
                {t('watchConfig.save')}
              </button>
              <button onClick={apply} disabled={applying} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 text-gray-700 text-[13px] font-medium hover:bg-gray-50 disabled:opacity-50" title={t('watchConfig.applyHint')}>
                {applying ? <Spinner size={12} /> : <UploadCloud size={13} />}
                {t('watchConfig.apply')}
              </button>
              <button onClick={resetDefaults} className="inline-flex items-center gap-1.5 px-3 py-2 text-[12px] text-gray-400 hover:text-gray-600 ml-auto">
                <RotateCcw size={12} /> {t('watchConfig.reset')}
              </button>
            </div>
            <p className="text-[11px] text-gray-400 mt-3">{t('watchConfig.applyHint')}</p>
          </>
        )}
      </div>
    </div>
  )
}
