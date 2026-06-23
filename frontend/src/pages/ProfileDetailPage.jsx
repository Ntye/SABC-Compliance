import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, Plus, X, Search, Pencil, Trash2,
  ChevronDown, ChevronRight, Lock, ListChecks,
  Layers, Save, FolderPlus, Copy, History, RotateCcw,
} from 'lucide-react'
import {
  getProfile, updateProfile, addProfileControl,
  updateProfileControl, deleteProfileControl, searchAllControls,
  getControlHistory, importScanControls, revertProfile, getUserRole,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'

const RISK = ['', 'High', 'Medium', 'Low']

const FIELDS = [
  { key: 'section_id',          label: 'sectionId',          kind: 'text' },
  { key: 'section',             label: 'section',             kind: 'text' },
  { key: 'title',               label: 'controlTitle',        kind: 'text' },
  { key: 'cis_id',              label: 'cisId',               kind: 'text' },
  { key: 'risk_profile',        label: 'riskProfile',         kind: 'risk' },
  { key: 'description',         label: 'description',         kind: 'area' },
  { key: 'recommended_value',   label: 'recommendedValue',    kind: 'area' },
  { key: 'agreed_value',        label: 'agreedValue',         kind: 'area' },
  { key: 'rationale',           label: 'rationale',           kind: 'area' },
  { key: 'validate_guideline',  label: 'validateGuideline',   kind: 'area' },
  { key: 'configure_guideline', label: 'configureGuideline',  kind: 'area' },
  { key: 'check_command',       label: 'checkCommand',        kind: 'code' },
  { key: 'regulatory',          label: 'regulatory',          kind: 'text' },
  { key: 'notes',               label: 'notes',               kind: 'area' },
]

function riskBadge(risk) {
  const r = (risk || '').toLowerCase()
  if (r === 'high')   return badge('danger')
  if (r === 'medium') return badge('warning')
  if (r === 'low')    return badge('info')
  return badge('gray')
}

function emptyControl(defaults = {}) {
  return {
    section_id: '', section: 'General', title: '', kind: 'control', cis_id: '',
    risk_profile: '', description: '', recommended_value: '', agreed_value: '',
    rationale: '', validate_guideline: '', configure_guideline: '',
    check_command: '', regulatory: '', notes: '', enabled: true,
    ...defaults,
  }
}

// ── Section hierarchy builder ──────────────────────────────────────────────────
// Parses section_ids to build a two-level tree:
//   topGroup (e.g. "C.1") → sectionNode (e.g. "1.1") → sub-sectionNode → controls
function buildTree(controls, query = '') {
  const q = query.trim().toLowerCase()
  const filtered = q
    ? controls.filter((c) =>
        [c.title, c.section, c.section_id, c.cis_id, c.description]
          .some((v) => (v || '').toLowerCase().includes(q)))
    : controls

  const sorted = [...filtered].sort((a, b) => a.position - b.position)

  function numParts(sid) {
    return (sid || '').split('.').filter((p) => /^\d+$/.test(p))
  }
  // "JR2.C.1.1.0" → "1.1"  (numeric parts, trailing 0 stripped)
  function nodeLabel(sid) {
    const p = numParts(sid)
    while (p.length > 1 && p[p.length - 1] === '0') p.pop()
    return p.join('.')
  }
  // "JR2.C.1.1.0" → "JR2.C.1"  (first 3 dot-parts)
  function groupKey(sid) { return (sid || '').split('.').slice(0, 3).join('.') }
  // "JR2.C.1" → "C.1"  (strip leading "JR2")
  function groupLabel(gk) {
    const p = gk.split('.').filter((x) => x !== 'JR2')
    return p.join('.')
  }

  const groupMap = new Map()
  const stack = []

  function getGroup(sid) {
    const gk = groupKey(sid)
    if (!groupMap.has(gk)) {
      groupMap.set(gk, { key: gk, label: groupLabel(gk), name: '', sections: [], orphans: [] })
    }
    return groupMap.get(gk)
  }

  for (const item of sorted) {
    const depth = numParts(item.section_id).length

    if (item.kind === 'section') {
      while (stack.length > 0 && stack[stack.length - 1].depth >= depth) stack.pop()

      const node = {
        id: item.id,
        sectionId: item.section_id,
        depth,
        label: nodeLabel(item.section_id),
        title: item.title || item.section,
        headerItem: item,
        children: [],
        controls: [],
      }

      if (stack.length === 0) {
        const group = getGroup(item.section_id)
        if (!group.name) group.name = node.title
        group.sections.push(node)
      } else {
        stack[stack.length - 1].children.push(node)
      }
      stack.push(node)
    } else {
      if (stack.length > 0) {
        stack[stack.length - 1].controls.push(item)
      } else {
        getGroup(item.section_id).orphans.push(item)
      }
    }
  }

  return [...groupMap.values()].sort((a, b) => a.key.localeCompare(b.key))
}

// ── Control row ───────────────────────────────────────────────────────────────
function ControlRow({ control: c, onEdit, onDelete, readOnly, t }) {
  return (
    <div className={`flex items-start gap-3 px-4 py-2.5 border-b border-gray-50 last:border-0 ${c.enabled ? '' : 'opacity-40'}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-mono text-gray-400">{c.section_id}</span>
          {c.cis_id && <span className={badge('cis')}>CIS {c.cis_id}</span>}
          {c.risk_profile && <span className={riskBadge(c.risk_profile)}>{c.risk_profile}</span>}
          {!c.enabled && <span className={badge('gray')}>{t('profiles.disabled')}</span>}
        </div>
        <div className="text-[12px] text-gray-800 font-medium mt-0.5 leading-snug">{c.title}</div>
        {c.agreed_value && (
          <div className="text-[11px] text-gray-500 mt-0.5">
            <span className="text-gray-400">{t('profiles.agreedValue')}:</span> {c.agreed_value}
          </div>
        )}
      </div>
      {!readOnly && (
        <div className="flex items-center gap-0.5 flex-shrink-0 pt-0.5">
          <button onClick={() => onEdit(c)} className="p-1.5 text-gray-300 hover:text-brand rounded" title={t('common.edit')}>
            <Pencil size={13} />
          </button>
          <button onClick={() => onDelete(c)} className="p-1.5 text-gray-300 hover:text-red-500 rounded" title={t('common.delete')}>
            <Trash2 size={13} />
          </button>
        </div>
      )}
    </div>
  )
}

// ── Recursive section node ────────────────────────────────────────────────────
function SectionNode({ node, onEdit, onDelete, readOnly, t, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  const totalControls = countControls(node)

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100/60 text-left"
      >
        {open
          ? <ChevronDown size={13} className="text-gray-400 flex-shrink-0" />
          : <ChevronRight size={13} className="text-gray-400 flex-shrink-0" />}
        <span className="text-[10px] font-mono font-semibold text-brand/60 flex-shrink-0 w-10">{node.label}</span>
        <span className="text-[12px] font-semibold text-gray-700 flex-1 truncate">{node.title}</span>
        <span className="text-[10px] text-gray-400 flex-shrink-0">{totalControls}</span>
      </button>

      {open && (
        <div className="ml-5 border-l border-gray-100 pl-3 mb-1">
          {node.controls.map((c) => (
            <ControlRow key={c.id} control={c} onEdit={onEdit} onDelete={onDelete} readOnly={readOnly} t={t} />
          ))}
          {node.children.map((child) => (
            <SectionNode key={child.id} node={child} onEdit={onEdit} onDelete={onDelete} readOnly={readOnly} t={t} defaultOpen={false} />
          ))}
        </div>
      )}
    </div>
  )
}

function countControls(node) {
  let n = node.controls.length
  for (const child of node.children) n += countControls(child)
  return n
}

// ── Top-level section group ───────────────────────────────────────────────────
function TopGroup({ group, onEdit, onDelete, onAdd, readOnly, t }) {
  const [open, setOpen] = useState(true)
  const total = group.sections.reduce((s, n) => s + countControls(n), 0) + group.orphans.length

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-gray-50/60 text-left"
      >
        {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
        <div className="w-7 h-7 rounded-md bg-brand/10 flex items-center justify-center flex-shrink-0">
          <span className="text-[9px] font-bold text-brand leading-none">{group.label}</span>
        </div>
        <span className="text-[13px] font-semibold text-gray-900 flex-1">{group.name}</span>
        <span className="text-[11px] text-gray-400 mr-2">{total} {t('profiles.controls')}</span>
      </button>

      {open && (
        <div className="px-4 pb-3 border-t border-gray-50 pt-2 space-y-0.5">
          {group.orphans.map((c) => (
            <ControlRow key={c.id} control={c} onEdit={onEdit} onDelete={onDelete} readOnly={readOnly} t={t} />
          ))}
          {group.sections.map((sec) => (
            <SectionNode
              key={sec.id}
              node={sec}
              onEdit={onEdit}
              onDelete={onDelete}
              readOnly={readOnly}
              t={t}
              defaultOpen={true}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Control history modal ─────────────────────────────────────────────────────
function HistoryModal({ profileId, control, onClose, onRestore, t }) {
  const [entries, setEntries] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getControlHistory(profileId, control.id)
      .then((r) => setEntries(r || []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [profileId, control.id])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="text-[14px] font-semibold text-gray-900">{t('profiles.controlHistory')}</h3>
            <p className="text-[11px] text-gray-500 mt-0.5">{control.title}</p>
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded"><X size={17} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && <div className="text-center py-8 text-[12px] text-gray-400">{t('common.loading')}</div>}
          {!loading && entries.length === 0 && (
            <div className="text-center py-8 text-[12px] text-gray-400">{t('profiles.historyEmpty')}</div>
          )}
          {entries.map((e) => (
            <div key={e.id} className="border border-gray-100 rounded-lg p-3 bg-gray-50/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] text-gray-500 font-mono">
                  {new Date(e.saved_at).toLocaleString()}
                </span>
                <button
                  onClick={() => { onRestore(e.snapshot); onClose() }}
                  className="flex items-center gap-1 text-[11px] text-brand hover:text-brand/80 font-medium"
                >
                  <RotateCcw size={11} /> {t('profiles.restore')}
                </button>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                {['title', 'cis_id', 'check_command', 'validate_guideline', 'agreed_value', 'notes'].map((k) =>
                  e.snapshot[k] ? (
                    <div key={k} className="col-span-2">
                      <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">{k.replace(/_/g, ' ')} </span>
                      <span className="text-[11px] text-gray-700 font-mono whitespace-pre-wrap break-all line-clamp-2">{e.snapshot[k]}</span>
                    </div>
                  ) : null
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Control add/edit drawer ───────────────────────────────────────────────────
function ControlDrawer({ control, profileId, onClose, onSave, saving, t }) {
  const [form, setForm] = useState(control)
  const [showHistory, setShowHistory] = useState(false)
  const isNew = !control.id
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  // Reuse picker — only shown when creating a new control
  const [reuseQ, setReuseQ]         = useState('')
  const [reuseHits, setReuseHits]   = useState([])
  const [reuseLoading, setReuseLoading] = useState(false)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (!isNew || reuseQ.length < 2) { setReuseHits([]); return }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setReuseLoading(true)
      try { setReuseHits((await searchAllControls(reuseQ, 12)) || []) }
      catch { setReuseHits([]) }
      finally { setReuseLoading(false) }
    }, 280)
    return () => clearTimeout(debounceRef.current)
  }, [reuseQ, isNew])

  function applyTemplate(src) {
    setForm((f) => ({
      ...f,
      section_id:          src.section_id,
      section:             src.section,
      title:               src.title,
      kind:                src.kind || 'control',
      cis_id:              src.cis_id || '',
      description:         src.description || '',
      recommended_value:   src.recommended_value || '',
      rationale:           src.rationale || '',
      validate_guideline:  src.validate_guideline || '',
      configure_guideline: src.configure_guideline || '',
      regulatory:          src.regulatory || '',
      risk_profile:        src.risk_profile || '',
      // agreed_value intentionally left as-is — operator fills in per-profile
    }))
    setReuseHits([])
    setReuseQ('')
  }

  const showSectionFields = form.kind === 'section'

  return (
    <>
    {showHistory && (
      <HistoryModal
        profileId={profileId}
        control={control}
        onClose={() => setShowHistory(false)}
        onRestore={(snap) => setForm((f) => ({ ...f, ...snap }))}
        t={t}
      />
    )}
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white w-full max-w-2xl h-full shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-[15px] font-semibold text-gray-900">
            {isNew ? t('profiles.addControl') : t('profiles.editControl')}
          </h3>
          <div className="flex items-center gap-1">
            {!isNew && (
              <button
                onClick={() => setShowHistory(true)}
                className="p-1.5 text-gray-400 hover:text-brand rounded"
                title={t('profiles.controlHistory')}
              >
                <History size={16} />
              </button>
            )}
            <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded"><X size={18} /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* ── Reuse picker (new controls only) ─────────────────────── */}
          {isNew && (
            <div className="px-6 pt-4 pb-3 border-b border-gray-100 bg-gray-50/50">
              <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                {t('profiles.searchExisting')}
              </p>
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={reuseQ}
                  onChange={(e) => setReuseQ(e.target.value)}
                  placeholder={t('profiles.searchExistingPlaceholder')}
                  className="w-full border border-gray-200 rounded-lg pl-8 pr-3 py-2 text-[12px] outline-none focus:border-brand bg-white"
                />
              </div>
              {reuseLoading && (
                <p className="text-[11px] text-gray-400 mt-1.5">{t('profiles.searching')}</p>
              )}
              {reuseHits.length > 0 && (
                <div className="mt-2 border border-gray-200 rounded-lg overflow-hidden bg-white divide-y divide-gray-50">
                  {reuseHits.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => applyTemplate(r)}
                      className="w-full text-left px-3 py-2 hover:bg-brand/5 group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-gray-400">{r.section_id}</span>
                        {r.cis_id && <span className="text-[10px] text-brand/60">CIS {r.cis_id}</span>}
                        <span className="ml-auto text-[10px] text-gray-300 group-hover:text-brand">
                          <Copy size={11} />
                        </span>
                      </div>
                      <div className="text-[12px] text-gray-700 truncate">{r.title}</div>
                    </button>
                  ))}
                </div>
              )}
              {reuseQ.length >= 2 && !reuseLoading && reuseHits.length === 0 && (
                <p className="text-[11px] text-gray-400 mt-1.5">{t('profiles.noExistingMatch')}</p>
              )}
            </div>
          )}

          {/* ── Form ────────────────────────────────────────────────── */}
          <div className="px-6 py-5 space-y-4">
            {/* Kind + enabled */}
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

            {/* Always-visible identity fields */}
            {['section_id', 'section', 'title'].map((key) => {
              const fld = FIELDS.find((f) => f.key === key)
              return (
                <div key={key}>
                  <label className="block text-[12px] font-medium text-gray-700 mb-1">{t(`profiles.${fld.label}`)}</label>
                  <input
                    value={form[key] || ''}
                    onChange={(e) => set(key, e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] outline-none focus:border-brand"
                  />
                </div>
              )
            })}

            {/* Extra fields — hidden for section headers since they don't carry check data */}
            {!showSectionFields && FIELDS.filter((f) => !['section_id', 'section', 'title'].includes(f.key)).map((fld) => (
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
                ) : fld.kind === 'code' ? (
                  <div>
                    <p className="text-[10px] text-gray-400 mb-1">{t('profiles.checkCommandHint')}</p>
                    <textarea
                      value={form[fld.key] || ''}
                      onChange={(e) => set(fld.key, e.target.value)}
                      rows={8}
                      spellCheck={false}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[11px] font-mono bg-gray-950 text-green-400 outline-none focus:border-brand resize-y"
                    />
                  </div>
                ) : fld.kind === 'area' ? (
                  <textarea
                    value={form[fld.key] || ''}
                    onChange={(e) => set(fld.key, e.target.value)}
                    rows={fld.key === 'validate_guideline' || fld.key === 'configure_guideline' ? 5 : 3}
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
        </div>

        {/* Footer */}
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
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function ProfileDetailPage() {
  const { id } = useParams()
  const t = useT()
  const toast = useToast()
  const isAdmin = getUserRole() === 'admin'
  const { data: profile, loading, error, refetch } = useApi(() => getProfile(id), { deps: [id] })

  const [query,      setQuery]      = useState('')
  const [editing,    setEditing]    = useState(null)
  const [saving,     setSaving]     = useState(false)
  const [importing,  setImporting]  = useState(false)
  const [reverting,  setReverting]  = useState(false)

  const tree = useMemo(
    () => buildTree(profile?.controls || [], query),
    [profile, query],
  )

  function openAdd(defaults = {}) {
    setEditing(emptyControl(defaults))
  }

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

  async function handleRevert() {
    if (!window.confirm(t('profiles.confirmRevert'))) return
    setReverting(true)
    try {
      await revertProfile(id)
      toast(t('profiles.reverted'), 'success')
      refetch()
    } catch (e) {
      toast(e.message || t('profiles.revertFailed'), 'error')
    } finally {
      setReverting(false)
    }
  }

  if (loading) return <div className="py-16 flex justify-center"><Spinner /></div>
  if (error)   return <div className="p-6 text-[13px] text-red-600 bg-red-50 rounded-lg m-6">{error}</div>
  if (!profile) return null

  // The CIS Benchmark is read-only for everyone; the internal referential and
  // custom profiles are editable by admins only.
  const readOnly = !isAdmin || !!profile.locked
  const canRevert = isAdmin && profile.framework === 'internal'

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <Link to="/profiles" className="inline-flex items-center gap-1.5 text-[12px] text-gray-500 hover:text-brand mb-4">
        <ArrowLeft size={14} /> {t('profiles.backToList')}
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 mb-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-[17px] font-semibold text-gray-900">{profile.name}</h2>
              {profile.source === 'builtin' ? (
                <>
                  <span className={badge('info')}><Lock size={9} className="mr-1" />{t('profiles.builtin')}</span>
                  {profile.locked
                    ? <span className={badge('gray')}>{t('profiles.readOnly')}</span>
                    : <span className={badge('internal')}>{t('profiles.adminEditable')}</span>}
                </>
              ) : (
                <span className={badge('gray')}>{t('profiles.custom')}</span>
              )}
            </div>
            {profile.description && (
              <p className="text-[12px] text-gray-500 mt-1.5 max-w-2xl">{profile.description}</p>
            )}
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

          <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
            {!readOnly && profile.source === 'builtin' && (
              <button
                onClick={async () => {
                  setImporting(true)
                  try {
                    const r = await importScanControls(id)
                    toast(t('profiles.importDone', { n: r.updated }), 'success')
                    refetch()
                  } catch (e) {
                    toast(e.message || t('profiles.importFailed'), 'error')
                  } finally { setImporting(false) }
                }}
                disabled={importing}
                className="flex items-center gap-1.5 border border-brand/30 bg-brand/5 text-brand text-[12px] font-medium px-3 py-2 rounded-lg hover:bg-brand/10 disabled:opacity-50"
              >
                {importing ? <Spinner size={12} /> : <History size={13} />}
                {importing ? t('profiles.importing') : t('profiles.importScanControls')}
              </button>
            )}
            {canRevert && (
              <button
                onClick={handleRevert}
                disabled={reverting}
                title={t('profiles.revertHint')}
                className="flex items-center gap-1.5 border border-amber-300 bg-amber-50 text-amber-700 text-[12px] font-medium px-3 py-2 rounded-lg hover:bg-amber-100 disabled:opacity-50"
              >
                {reverting ? <Spinner size={12} /> : <RotateCcw size={13} />}
                {reverting ? t('profiles.reverting') : t('profiles.revertToOriginal')}
              </button>
            )}
            {!readOnly && (
              <>
                <button
                  onClick={() => openAdd({ kind: 'section' })}
                  className="flex items-center gap-1.5 border border-gray-200 text-gray-600 text-[12px] font-medium px-3 py-2 rounded-lg hover:bg-gray-50"
                >
                  <FolderPlus size={14} />{t('profiles.addSection')}
                </button>
                <button
                  onClick={() => openAdd()}
                  className="flex items-center gap-1.5 bg-brand text-white text-[12px] font-medium px-3.5 py-2 rounded-lg hover:bg-brand/90"
                >
                  <Plus size={14} />{t('profiles.addControl')}
                </button>
              </>
            )}
          </div>
        </div>

        {readOnly && (
          <div className="mt-4 flex items-center gap-2 text-[12px] text-gray-500 bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
            <Lock size={12} className="text-gray-400 flex-shrink-0" />
            {profile.locked ? t('profiles.cisReadOnlyNotice') : t('profiles.adminOnlyNotice')}
          </div>
        )}
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

      {/* Hierarchy tree */}
      <div className="space-y-3">
        {tree.map((group) => (
          <TopGroup
            key={group.key}
            group={group}
            onEdit={setEditing}
            onDelete={handleDelete}
            onAdd={openAdd}
            readOnly={readOnly}
            t={t}
          />
        ))}
        {tree.length === 0 && (
          <div className="text-center py-16 text-[13px] text-gray-400">{t('profiles.noControls')}</div>
        )}
      </div>

      {editing && (
        <ControlDrawer
          control={editing}
          profileId={id}
          onClose={() => setEditing(null)}
          onSave={handleSave}
          saving={saving}
          t={t}
        />
      )}
    </div>
  )
}
