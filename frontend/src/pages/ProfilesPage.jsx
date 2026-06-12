import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, X, FileCode, Layers, ListChecks, Lock, Trash2, ChevronRight } from 'lucide-react'
import { listProfiles, createProfile, deleteProfile } from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl border border-gray-100 shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-[14px] font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function ProfilesPage() {
  const t = useT()
  const toast = useToast()
  const navigate = useNavigate()
  const { data: profiles, loading, error, refetch } = useApi(listProfiles)

  const [showCreate, setShowCreate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [osFamily, setOsFamily] = useState('linux')

  async function handleCreate() {
    if (!name.trim()) {
      toast(t('profiles.nameRequired'), 'error')
      return
    }
    setSaving(true)
    try {
      const created = await createProfile({ name: name.trim(), description: description.trim() || null, os_family: osFamily })
      toast(t('profiles.created'), 'success')
      setShowCreate(false)
      setName(''); setDescription(''); setOsFamily('linux')
      navigate(`/profiles/${created.id}`)
    } catch (e) {
      toast(e.message || t('profiles.createFailed'), 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(p, e) {
    e.stopPropagation()
    if (!window.confirm(t('profiles.confirmDelete', { name: p.name }))) return
    try {
      await deleteProfile(p.id)
      toast(t('profiles.deleted'), 'success')
      refetch()
    } catch (err) {
      toast(err.message || t('profiles.deleteFailed'), 'error')
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900">{t('profiles.title')}</h2>
          <p className="text-[13px] text-gray-500 mt-0.5">{t('profiles.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 bg-brand text-white text-[12px] font-medium px-3.5 py-2 rounded-lg hover:bg-brand/90 transition-colors"
        >
          <Plus size={14} />
          {t('profiles.newProfile')}
        </button>
      </div>

      {loading && <div className="py-16 flex justify-center"><Spinner /></div>}
      {error && <div className="text-[13px] text-red-600 bg-red-50 rounded-lg p-4">{error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(profiles || []).map((p) => (
            <div
              key={p.id}
              onClick={() => navigate(`/profiles/${p.id}`)}
              className="group bg-white border border-gray-100 rounded-xl p-5 hover:border-brand/40 hover:shadow-sm cursor-pointer transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-brand/10 flex items-center justify-center flex-shrink-0">
                    <FileCode size={17} className="text-brand" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-[14px] font-semibold text-gray-900 truncate">{p.name}</h3>
                      {p.source === 'builtin'
                        ? <span className={badge('info')}><Lock size={9} className="mr-1" />{t('profiles.builtin')}</span>
                        : <span className={badge('gray')}>{t('profiles.custom')}</span>}
                    </div>
                    <div className="text-[11px] text-gray-400 mt-0.5">v{p.version} · {p.os_family}</div>
                  </div>
                </div>
                <ChevronRight size={16} className="text-gray-300 group-hover:text-brand transition-colors flex-shrink-0" />
              </div>

              {p.description && (
                <p className="text-[12px] text-gray-500 mt-3 line-clamp-2">{p.description}</p>
              )}

              <div className="flex items-center gap-4 mt-4 pt-3 border-t border-gray-50">
                <span className="flex items-center gap-1.5 text-[12px] text-gray-600">
                  <ListChecks size={13} className="text-gray-400" />
                  {p.control_count} {t('profiles.controls')}
                </span>
                <span className="flex items-center gap-1.5 text-[12px] text-gray-600">
                  <Layers size={13} className="text-gray-400" />
                  {p.section_count} {t('profiles.sections')}
                </span>
                {p.source !== 'builtin' && (
                  <button
                    onClick={(e) => handleDelete(p, e)}
                    className="ml-auto p-1.5 text-gray-300 hover:text-red-500 rounded transition-colors"
                    title={t('common.delete')}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}

          {(profiles || []).length === 0 && (
            <div className="col-span-full text-center py-16 text-[13px] text-gray-400">
              {t('profiles.empty')}
            </div>
          )}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <Modal title={t('profiles.newProfile')} onClose={() => setShowCreate(false)}>
          <div className="space-y-4">
            <div>
              <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('profiles.name')}</label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('profiles.namePlaceholder')}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('profiles.description')}</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand resize-none"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('profiles.osFamily')}</label>
              <select
                value={osFamily}
                onChange={(e) => setOsFamily(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand"
              >
                <option value="linux">Linux</option>
                <option value="windows">Windows</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowCreate(false)} className="px-3.5 py-2 text-[12px] font-medium text-gray-600 hover:bg-gray-100 rounded-lg">
                {t('common.cancel')}
              </button>
              <button onClick={handleCreate} disabled={saving} className="px-3.5 py-2 text-[12px] font-medium bg-brand text-white rounded-lg hover:bg-brand/90 disabled:opacity-50">
                {saving ? t('common.saving') : t('common.create')}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
