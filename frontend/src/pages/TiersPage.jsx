import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Gauge, Plus, Pencil, Trash2, ShieldCheck, Server, Layers, X, Lock,
} from 'lucide-react'
import {
  listTiers, createTier, updateTier, deleteTier,
  assignNodeTier, assignGroupTier, enforceReferential,
  getClosedLoopSetting, setClosedLoopSetting,
  listNodes, listNodeGroups, getUserRole,
} from '../lib/api.js'
import { useT } from '../context/LangContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { badge, btn, btnSm, btnDangerSm } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import EmptyState from '../components/common/EmptyState.jsx'
import ConfirmDialog from '../components/common/ConfirmDialog.jsx'

function scopeLabel(tier, t) {
  const extras = tier.extra_control_ids?.length || 0
  if (tier.includes_level_2) return t('tiers.level1And2')
  if (extras > 0) return `${t('tiers.level1Only')} · ${t('tiers.extraControls', { n: extras })}`
  return t('tiers.level1Only')
}

// ── Create / edit modal ───────────────────────────────────────────────────────

function TierFormModal({ tier, onClose, onSaved }) {
  const t = useT()
  const toast = useToast()
  const editing = !!tier
  const [name, setName] = useState(tier?.name || '')
  const [description, setDescription] = useState(tier?.description || '')
  const [includesL2, setIncludesL2] = useState(tier?.includes_level_2 || false)
  const [extra, setExtra] = useState((tier?.extra_control_ids || []).join(', '))
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!name.trim()) { toast(t('tiers.name'), 'error'); return }
    setSaving(true)
    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      includes_level_2: includesL2,
      extra_control_ids: includesL2
        ? []
        : extra.split(',').map((s) => s.trim()).filter(Boolean),
    }
    try {
      if (editing) await updateTier(tier.id, payload)
      else await createTier(payload)
      toast(editing ? t('tiers.editTier') : t('tiers.createTier'), 'success')
      onSaved()
    } catch (e) {
      toast(e.message || 'Error', 'error')
    } finally {
      setSaving(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h3 className="text-[15px] font-semibold text-gray-900">
            {editing ? t('tiers.editTier') : t('tiers.createTier')}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={18} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('tiers.name')}</label>
            <input
              value={name} onChange={(e) => setName(e.target.value)} autoFocus
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand"
              placeholder="Tier 1.5"
            />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('tiers.descriptionOptional')}</label>
            <input
              value={description} onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg outline-none focus:border-brand"
            />
          </div>
          <label className="flex items-start gap-2 cursor-pointer">
            <input type="checkbox" checked={includesL2} onChange={(e) => setIncludesL2(e.target.checked)} className="mt-0.5" />
            <span>
              <span className="text-[13px] font-medium text-gray-800">{t('tiers.includesLevel2')}</span>
              <span className="block text-[11px] text-gray-400">{t('tiers.includesLevel2Hint')}</span>
            </span>
          </label>
          {!includesL2 && (
            <div>
              <label className="block text-[12px] font-medium text-gray-700 mb-1">{t('tiers.extraControlIds')}</label>
              <textarea
                value={extra} onChange={(e) => setExtra(e.target.value)} rows={2}
                className="w-full px-3 py-2 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand"
                placeholder="1.1.2.3, 5.4.1"
              />
              <p className="text-[11px] text-gray-400 mt-1">{t('tiers.extraControlIdsHint')}</p>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-gray-100">
          <button onClick={onClose} className={btnSm(false)}>{t('detection.close')}</button>
          <button onClick={save} disabled={saving} className={btnSm(true)}>
            {saving ? <Spinner size={11} /> : null}
            {editing ? t('tiers.editTier') : t('tiers.createTier')}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TiersPage() {
  const t = useT()
  const toast = useToast()
  const role = getUserRole()
  const isAdmin = role === 'admin'
  const canOperate = role === 'admin' || role === 'operator'

  const [tiers, setTiers] = useState([])
  const [nodes, setNodes] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [closedLoop, setClosedLoop] = useState(false)
  const [savingLoop, setSavingLoop] = useState(false)

  const [formTier, setFormTier] = useState(undefined)  // undefined=closed, null=create, obj=edit
  const [confirmDel, setConfirmDel] = useState(null)

  // Assign / enforce panel state
  const [targetKind, setTargetKind] = useState('node')  // 'node' | 'group'
  const [targetId, setTargetId] = useState('')
  const [assignTierId, setAssignTierId] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const [ts, ns, gs, cl] = await Promise.all([
        listTiers(), listNodes(), listNodeGroups(), getClosedLoopSetting().catch(() => ({ enabled: false })),
      ])
      setTiers(ts)
      setNodes(ns)
      setGroups(gs)
      setClosedLoop(!!cl.enabled)
    } catch (e) {
      toast(e.message || 'Error', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const nodeCountByTier = useMemo(() => {
    const m = {}
    for (const n of nodes) {
      const tid = n.tier_id || 'tier-non-critical'
      m[tid] = (m[tid] || 0) + 1
    }
    return m
  }, [nodes])

  async function toggleClosedLoop(next) {
    setSavingLoop(true)
    try {
      await setClosedLoopSetting(next)
      setClosedLoop(next)
      toast(next ? t('tiers.closedLoopOn') : t('tiers.closedLoopOff'), 'success')
    } catch (e) {
      toast(e.message || 'Error', 'error')
    } finally {
      setSavingLoop(false)
    }
  }

  async function doDelete() {
    const tier = confirmDel
    setConfirmDel(null)
    try {
      await deleteTier(tier.id)
      toast(t('tiers.deleteTitle'), 'success')
      load()
    } catch (e) {
      toast(e.message || 'Error', 'error')
    }
  }

  async function doAssign() {
    if (!targetId) { toast(t('tiers.needTarget'), 'error'); return }
    if (!assignTierId) { toast(t('tiers.needTier'), 'error'); return }
    setBusy(true)
    try {
      if (targetKind === 'node') {
        await assignNodeTier(targetId, assignTierId)
        toast(t('tiers.assigned'), 'success')
      } else {
        const res = await assignGroupTier(targetId, assignTierId)
        toast(t('tiers.assignedGroup', { n: res.assigned ?? 0 }), 'success')
      }
      load()
    } catch (e) {
      toast(e.message || 'Error', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function doEnforce() {
    if (!targetId) { toast(t('tiers.needTarget'), 'error'); return }
    setBusy(true)
    try {
      const res = await enforceReferential(
        targetKind === 'node' ? { nodeId: targetId } : { groupId: targetId },
      )
      toast(t('tiers.enforceLaunched', { n: res.launched ?? (res.jobs?.length || 0) }), 'success')
    } catch (e) {
      toast(e.message || 'Error', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-[18px] font-semibold text-gray-900 flex items-center gap-2">
            <Gauge size={17} className="text-brand" />
            {t('tiers.title')}
          </h2>
          <p className="text-[12px] text-gray-400 mt-0.5 max-w-2xl">{t('tiers.subtitle')}</p>
        </div>
        {isAdmin && (
          <button onClick={() => setFormTier(null)} className={btn(true)}>
            <Plus size={14} /> {t('tiers.newTier')}
          </button>
        )}
      </div>

      {/* Global closed-loop toggle */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 mb-5 flex items-center justify-between">
        <div className="min-w-0 pr-4">
          <div className="text-[13px] font-semibold text-gray-800">{t('tiers.closedLoopTitle')}</div>
          <p className="text-[11px] text-gray-400 mt-0.5">{t('tiers.closedLoopHint')}</p>
        </div>
        <button
          disabled={!isAdmin || savingLoop}
          onClick={() => toggleClosedLoop(!closedLoop)}
          className={`shrink-0 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-[12px] font-medium border ${
            closedLoop ? 'border-green-600/30 text-green-700 bg-green-50' : 'border-gray-200 text-gray-500'
          } ${!isAdmin ? 'opacity-60 cursor-not-allowed' : ''}`}
          title={!isAdmin ? t('tiers.systemImmutable') : ''}
        >
          <span className={`w-2 h-2 rounded-full ${closedLoop ? 'bg-green-500' : 'bg-gray-300'}`} />
          {closedLoop ? t('tiers.closedLoopOn') : t('tiers.closedLoopOff')}
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-14 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      ) : tiers.length === 0 ? (
        <EmptyState icon={Gauge} title={t('tiers.empty')} description={t('tiers.subtitle')} />
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden mb-6">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-100">
                {[t('tiers.colTier'), t('tiers.colScope'), t('tiers.colKind'), t('tiers.colNodes'), t('tiers.colActions')].map((h, i) => (
                  <th key={i} className="text-left px-4 py-2.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {tiers.map((tier) => (
                <tr key={tier.id} className="hover:bg-gray-50/60">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-800">{tier.name}</div>
                    {tier.description && <div className="text-[11px] text-gray-400">{tier.description}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-gray-600">
                      <ShieldCheck size={12} className="text-gray-400" />
                      {scopeLabel(tier, t)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={badge(tier.is_system ? 'gray' : 'internal')}>
                      {tier.is_system ? t('tiers.system') : t('tiers.custom')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{nodeCountByTier[tier.id] || 0}</td>
                  <td className="px-4 py-3">
                    {tier.is_system ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-gray-300" title={t('tiers.systemImmutable')}>
                        <Lock size={11} />
                      </span>
                    ) : isAdmin ? (
                      <div className="flex items-center gap-2">
                        <button onClick={() => setFormTier(tier)} className={btnSm(false)}>
                          <Pencil size={11} /> {t('tiers.editTier')}
                        </button>
                        <button onClick={() => setConfirmDel(tier)} className={btnDangerSm}>
                          <Trash2 size={11} />
                        </button>
                      </div>
                    ) : <span className="text-gray-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Assign & enforce */}
      {canOperate && (
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="text-[14px] font-semibold text-gray-800 flex items-center gap-2">
            <Layers size={15} className="text-brand" /> {t('tiers.assignTitle')}
          </h3>
          <p className="text-[11px] text-gray-400 mt-0.5 mb-4">{t('tiers.assignSubtitle')}</p>

          <div className="flex flex-wrap items-end gap-3">
            {/* Target kind toggle */}
            <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
              {['node', 'group'].map((k) => (
                <button
                  key={k}
                  onClick={() => { setTargetKind(k); setTargetId('') }}
                  className={`px-3 py-2 text-[12px] font-medium inline-flex items-center gap-1.5 ${
                    targetKind === k ? 'bg-brand text-white' : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {k === 'node' ? <Server size={12} /> : <Layers size={12} />}
                  {k === 'node' ? t('tiers.targetNode') : t('tiers.targetGroup')}
                </button>
              ))}
            </div>

            {/* Target select */}
            <div className="min-w-[200px]">
              <select
                value={targetId} onChange={(e) => setTargetId(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white text-gray-700"
              >
                <option value="">{targetKind === 'node' ? t('tiers.pickNode') : t('tiers.pickGroup')}</option>
                {(targetKind === 'node' ? nodes : groups).map((o) => (
                  <option key={o.id} value={o.id}>{o.hostname || o.name}</option>
                ))}
              </select>
            </div>

            {/* Tier select */}
            <div className="min-w-[160px]">
              <select
                value={assignTierId} onChange={(e) => setAssignTierId(e.target.value)}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white text-gray-700"
              >
                <option value="">{t('tiers.pickTier')}</option>
                {tiers.map((tr) => <option key={tr.id} value={tr.id}>{tr.name}</option>)}
              </select>
            </div>

            <button onClick={doAssign} disabled={busy} className={btnSm(true)}>
              {busy ? <Spinner size={11} /> : <Gauge size={12} />} {t('tiers.assign')}
            </button>
            <button onClick={doEnforce} disabled={busy} className={btnSm(false)} title={t('tiers.enforceHint')}>
              <ShieldCheck size={12} /> {t('tiers.enforce')}
            </button>
          </div>
          <p className="text-[11px] text-gray-400 mt-3">{t('tiers.enforceHint')}</p>
        </div>
      )}

      {formTier !== undefined && (
        <TierFormModal
          tier={formTier}
          onClose={() => setFormTier(undefined)}
          onSaved={() => { setFormTier(undefined); load() }}
        />
      )}

      <ConfirmDialog
        open={!!confirmDel}
        title={t('tiers.deleteTitle')}
        message={t('tiers.deleteMsg')}
        confirmLabel={t('tiers.deleteTitle')}
        danger
        onCancel={() => setConfirmDel(null)}
        onConfirm={doDelete}
      />
    </div>
  )
}
