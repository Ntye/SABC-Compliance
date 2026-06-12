import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Plus, X, Search, Pencil, Trash2, ChevronDown, ChevronRight,
  Lock, ListChecks, Layers, Save,
} from 'lucide-react'
import {
  getProfile, updateProfile, addProfileControl, updateProfileControl, deleteProfileControl,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

const RISK = ['', 'High', 'Medium', 'Low']

// Fields shown in the edit drawer, in order. Long-text fields get a textarea.
const FIELDS = [
  { key: 'section_id', label: 'sectionId', kind: 'text' },
  { key: 'section', label: 'section', kind: 'text' },
  { key: 'title', label: 'controlTitle', kind: 'text' },
  { key: 'cis_id', label: 'cisId', kind: 'text' },
  { key: 'risk_profile', label: 'riskProfile', kind: 'risk' },
  { key: 'description', label: 'description', kind: 'area' },
  { key: 'recommended_value', label: 'recommendedValue', kind: 'area' },
  { key: 'agreed_value', label: 'agreedValue', kind: 'area' },
  { key: 'rationale', label: 'rationale', kind: 'area' },
  { key: 'validate_guideline', label: 'validateGuideline', kind: 'area' },
  { key: 'configure_guideline', label: 'configureGuideline', kind: 'area' },
  { key: 'regulatory', label: 'regulatory', kind: 'text' },
  { key: 'notes', label: 'notes', kind: 'area' },
]

function riskBadge(risk) {
  const r = (risk || '').toLowerCase()
  if (r === 'high') return badge('danger')
  if (r === 'medium') return badge('warning')
  if (r === 'low') return badge('info')
  return badge('gray')
}

function emptyControl() {
  return {
    section_id: '', section: 'General', title: '', kind: 'control', cis_id: '',
    risk_profile: '', description: '', recommended_value: '', agreed_value: '',
    rationale: '', validate_guideline: '', configure_guideline: '', regulatory: '',
    notes: '', enabled: true,
  }
}

// ── Edit / Add control drawer ───────────────────────────────────────────────────
function ControlDrawer({ control, onClose, onSave, saving, t }) {
  const [form, setForm] = useState(control)
  const isNew = !control.id
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white w-full max-w-2xl h-full shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-[15px] font-semibold text-gray-900">
            {isNew ? t('profiles.addControl') : t('profiles.editControl')}
          </h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-[12px] font-medium text-gray-700">
              <input type="checkbox" checked={!!form.enabled} onChange={(e) => set('enabled', e.target.checked)} className="rounded" />
              {t('profiles.enabled')}
            </label>
            <select
              value={form.kind || 'control'}
              onChange={(e) => set('kind', e.target.value)}
              className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-[12px] outline-none focus:border-brand"
            >
              <option value="control">{t('profiles.kindControl')}</option>
              <option value="section">{t('profiles.kindSection')}</option>
            </select>
          </div>

          {FIELDS.map((fld) => (
            <div key={fld.key}>
              <label className="block text-[12px] font-medium text-gray-700 mb-1">{t(`profiles.${fld.label}`)}</label>
              {fld.kind === 'risk' ? (
                <select
                  value={form[fld.key] || ''}
                  onChange={(e) => set(fld.key, e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand"
                >
                  {RISK.map((r) => <option key={r} value={r}>{r || '—'}</option>)}
                </select>
              ) : fld.kind === 'area' ? (
                <textarea
                  value={form[fld.key] || ''}
                  onChange={(e) => set(fld.key, e.target.value)}
                  rows={fld.key === 'validate_guideline' || fld.key === 'configure_guideline' ? 6 : 3}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[12px] font-mono outline-none focus:border-brand resize-y"
                />
              ) : (
                <input
                  value={form[fld.key] || ''}
                  onChange={(e) => set(fld.key, e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand"
                />
              )}
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">
          <button onClick={onClose} className="px-3.5 py-2 text-[12px] font-medium text-gray-600 hover:bg-gray-100 rounded-lg">
            {t('common.cancel')}
          </button>
          <button
            onClick={() => onSave(form)}
            disabled={saving || !form.title?.trim()}
            className="flex items-center gap-1.5 px-3.5 py-2 text-[12px] font-medium bg-brand text-white rounded-lg hover:bg-brand/90 disabled:opacity-50"
          >
            <Save size={13} />
            {saving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── A collapsible section of controls ───────────────────────────────────────────
function SectionGroup({ section, controls, onEdit, onDelete, readOnly, t }) {
  const [open, setOpen] = useState(true)
  const active = controls.filter((c) => c.enabled).length
  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-2 px-5 py-3 hover:bg-gray-50/50 text-left">
        {open ? <ChevronDown size={15} className="text-gray-400" /> : <ChevronRight size={15} className="text-gray-400" />}
        <span className="text-[13px] font-semibold text-gray-800 flex-1">{section}</span>
        <span className="text-[11px] text-gray-400">{active}/{controls.length} {t('profiles.active')}</span>
      </button>
      {open && (
        <div className="divide-y divide-gray-50">
          {controls.map((c) => (
            <div key={c.id} className={`flex items-start gap-3 px-5 py-3 ${c.enabled ? '' : 'opacity-50'}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-mono text-gray-400">{c.section_id}</span>
                  {c.cis_id && <span className={badge('cis')}>CIS {c.cis_id}</span>}
                  {c.risk_profile && <span className={riskBadge(c.risk_profile)}>{c.risk_profile}</span>}
                  {c.kind === 'section' && <span className={badge('gray')}>{t('profiles.kindSection')}</span>}
                  {!c.enabled && <span className={badge('gray')}>{t('profiles.disabled')}</span>}
                </div>
                <div className="text-[13px] text-gray-800 font-medium mt-0.5">{c.title}</div>
                {c.agreed_value && (
                  <div className="text-[11px] text-gray-500 mt-0.5">
                    <span className="text-gray-400">{t('profiles.agreedValue')}:</span> {c.agreed_value}
                  </div>
                )}
              </div>
              {!readOnly && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => onEdit(c)} className="p-1.5 text-gray-300 hover:text-brand rounded" title={t('common.edit')}>
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => onDelete(c)} className="p-1.5 text-gray-300 hover:text-red-500 rounded" title={t('common.delete')}>
                    <Trash2 size={14} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ProfileDetailPage() {
  const { id } = useParams()
  const t = useT()
  const toast = useToast()
  const { data: profile, loading, error, refetch } = useApi(() => getProfile(id), { deps: [id] })

  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState(null)   // control being edited/added
  const [saving, setSaving] = useState(false)

  const grouped = useMemo(() => {
    const controls = profile?.controls || []
    const q = query.trim().toLowerCase()
    const filtered = q
      ? controls.filter((c) =>
          [c.title, c.section, c.section_id, c.cis_id, c.description]
            .some((v) => (v || '').toLowerCase().includes(q)))
      : controls
    const map = new Map()
    for (const c of filtered) {
      const key = c.section || 'General'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(c)
    }
    return [...map.entries()]
  }, [profile, query])

  async function handleSave(form) {
    setSaving(true)
    try {
      if (form.id) {
        await updateProfileControl(id, form.id, form)
        toast(t('profiles.controlSaved'), 'success')
      } else {
        await addProfileControl(id, form)
        toast(t('profiles.controlAdded'), 'success')
      }
      setEditing(null)
      refetch()
    } catch (e) {
      toast(e.message || t('profiles.saveFailed'), 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(c) {
    if (!window.confirm(t('profiles.confirmDeleteControl', { name: c.title }))) return
    try {
      await deleteProfileControl(id, c.id)
      toast(t('profiles.controlDeleted'), 'success')
      refetch()
    } catch (e) {
      toast(e.message || t('profiles.deleteFailed'), 'error')
    }
  }

  if (loading) return <div className="py-16 flex justify-center"><Spinner /></div>
  if (error) return <div className="p-6 text-[13px] text-red-600 bg-red-50 rounded-lg m-6">{error}</div>
  if (!profile) return null

  const readOnly = false  // built-in profiles are editable too (operator edits persist)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <Link to="/profiles" className="inline-flex items-center gap-1.5 text-[12px] text-gray-500 hover:text-brand mb-4">
        <ArrowLeft size={14} /> {t('profiles.backToList')}
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 mb-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-[17px] font-semibold text-gray-900">{profile.name}</h2>
              {profile.source === 'builtin'
                ? <span className={badge('info')}><Lock size={9} className="mr-1" />{t('profiles.builtin')}</span>
                : <span className={badge('gray')}>{t('profiles.custom')}</span>}
            </div>
            {profile.description && <p className="text-[12px] text-gray-500 mt-1.5 max-w-2xl">{profile.description}</p>}
            <div className="flex items-center gap-4 mt-3">
              <span className="flex items-center gap-1.5 text-[12px] text-gray-600">
                <ListChecks size={13} className="text-gray-400" />{profile.control_count} {t('profiles.controls')}
              </span>
              <span className="flex items-center gap-1.5 text-[12px] text-gray-600">
                <Layers size={13} className="text-gray-400" />{profile.section_count} {t('profiles.sections')}
              </span>
              <span className="text-[12px] text-gray-400">v{profile.version} · {profile.os_family}</span>
            </div>
          </div>
          <button
            onClick={() => setEditing(emptyControl())}
            className="flex items-center gap-1.5 bg-brand text-white text-[12px] font-medium px-3.5 py-2 rounded-lg hover:bg-brand/90 flex-shrink-0"
          >
            <Plus size={14} />{t('profiles.addControl')}
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('profiles.searchControls')}
          className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-[13px] outline-none focus:border-brand"
        />
      </div>

      {/* Sections */}
      <div className="space-y-3">
        {grouped.map(([section, controls]) => (
          <SectionGroup
            key={section}
            section={section}
            controls={controls}
            onEdit={setEditing}
            onDelete={handleDelete}
            readOnly={readOnly}
            t={t}
          />
        ))}
        {grouped.length === 0 && (
          <div className="text-center py-16 text-[13px] text-gray-400">{t('profiles.noControls')}</div>
        )}
      </div>

      {editing && (
        <ControlDrawer
          control={editing}
          onClose={() => setEditing(null)}
          onSave={handleSave}
          saving={saving}
          t={t}
        />
      )}
    </div>
  )
}
