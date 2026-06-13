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
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900">{t('profiles.title')}</h2>
          <p className="text-[13px] text-gray-500 mt-0.5">{t('profiles.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 bg-brand text-white text-[12px] font-medium px-3.5 py-2 rounded-lg hover:bg-brand/90 transition-colors flex-shrink-0"
        >
          <Plus size={14} />
          {t('profiles.newProfile')}
        </button>
      </div>

      {loading && <div className="py-16 flex justify-center"><Spinner /></div>}
      {error && <div className="text-[13px] text-red-600 bg-red-50 rounded-lg p-4">{error}</div>}

      {!loading && !error && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {(profiles || []).length === 0 ? (
            <div className="py-16 text-center text-[13px] text-gray-400">{t('profiles.empty')}</div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-5 py-2.5">{t('profiles.name')}</th>
                  <th className="text-left px-5 py-2.5">{t('profiles.osFamily')}</th>
                  <th className="text-left px-5 py-2.5 hidden sm:table-cell">Version</th>
                  <th className="text-left px-5 py-2.5">{t('profiles.controls')} / {t('profiles.sections')}</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {(profiles || []).map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/profiles/${p.id}`)}
                    className="hover:bg-gray-50/50 cursor-pointer group"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center flex-shrink-0">
                          <FileCode size={15} className="text-brand" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-gray-800">{p.name}</span>
                            {p.source === 'builtin'
                              ? <span className={badge('info')}><Lock size={9} className="mr-1" />{t('profiles.builtin')}</span>
                              : <span className={badge('gray')}>{t('profiles.custom')}</span>}
                          </div>
                          {p.description && (
                            <div className="text-[11px] text-gray-400 truncate max-w-[340px] mt-0.5">{p.description}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{p.os_family}</td>
                    <td className="px-5 py-3 text-gray-400 hidden sm:table-cell">v{p.version}</td>
                    <td className="px-5 py-3">
                      <span className="flex items-center gap-3 text-gray-600">
                        <span className="flex items-center gap-1">
                          <ListChecks size={12} className="text-gray-400" />
                          <b>{p.control_count}</b>
                        </span>
                        <span className="flex items-center gap-1">
                          <Layers size={12} className="text-gray-400" />
                          <b>{p.section_count}</b>
                        </span>
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {p.source !== 'builtin' && (
                          <button
                            onClick={(e) => handleDelete(p, e)}
                            className="p-1.5 text-gray-300 hover:text-red-500 rounded transition-colors"
                            title={t('common.delete')}
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                        <ChevronRight size={15} className="text-gray-300 group-hover:text-brand transition-colors" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
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
