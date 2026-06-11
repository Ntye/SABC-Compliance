import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Plus, Trash2, X, Search, CheckCircle, XCircle, Server, ChevronRight,
  ChevronLeft, ArrowLeft, Pin, GitBranch, Check,
} from 'lucide-react'
import {
  listNodeGroups, createNodeGroup, deleteNodeGroup, listNodes,
  listNodeGroupFacts, previewNodeGroupMatches,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import Spinner from '../components/common/Spinner.jsx'

const OPERATORS = ['=', '!=', '~', '>', '>=', '<', '<=']

function SyncIcon({ ok }) {
  return ok
    ? <CheckCircle size={14} className="text-green-500" />
    : <XCircle size={14} className="text-red-400" />
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-xl border border-gray-100 shadow-xl mx-4 p-6 w-full max-w-md">
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

function relativeTime(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString()
}

// ── Stepper header ────────────────────────────────────────────────────────────
function Stepper({ step, labels }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {labels.map((label, i) => {
        const n = i + 1
        const done = step > n
        const active = step === n
        return (
          <div key={label} className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <span className={[
                'flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-semibold',
                active ? 'bg-brand text-white'
                  : done ? 'bg-green-500 text-white'
                  : 'bg-gray-100 text-gray-400',
              ].join(' ')}>
                {done ? <Check size={13} /> : n}
              </span>
              <span className={[
                'text-[12px] font-medium',
                active ? 'text-gray-900' : 'text-gray-400',
              ].join(' ')}>{label}</span>
            </div>
            {n < labels.length && <ChevronRight size={14} className="text-gray-300" />}
          </div>
        )
      })}
    </div>
  )
}

// ── Create wizard ─────────────────────────────────────────────────────────────
function CreateWizard({ groups, nodes, facts, onCancel, onCreated }) {
  const t = useT()
  const toast = useToast()
  const [step, setStep] = useState(1)
  const [saving, setSaving] = useState(false)

  // Step 1 — details
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [parent, setParent] = useState('All Nodes')
  const [environment, setEnvironment] = useState('production')
  const [isEnvGroup, setIsEnvGroup] = useState(false)

  // Step 2 — rules & pins
  const [matchType, setMatchType] = useState('all')
  const [rules, setRules] = useState([])
  const [pinnedIds, setPinnedIds] = useState([])
  const [nodeSearch, setNodeSearch] = useState('')

  // draft rule row
  const [draftFact, setDraftFact] = useState('')
  const [draftOp, setDraftOp] = useState('=')
  const [draftVal, setDraftVal] = useState('')

  // live preview of matching node ids
  const [matchIds, setMatchIds] = useState([])

  const parentOptions = useMemo(
    () => ['All Nodes', ...(groups || []).map((g) => g.name)],
    [groups],
  )

  const factValues = useMemo(() => {
    const f = (facts || []).find((x) => x.name === draftFact)
    return f ? f.values : []
  }, [facts, draftFact])

  const filteredNodes = useMemo(() => {
    if (!nodes) return []
    const q = nodeSearch.toLowerCase()
    if (!q) return nodes
    return nodes.filter((n) =>
      (n.hostname || '').toLowerCase().includes(q) || (n.ip || '').toLowerCase().includes(q))
  }, [nodes, nodeSearch])

  // Recompute matches whenever rules / match type / pins change
  const refreshMatches = useCallback(async () => {
    try {
      const ids = await previewNodeGroupMatches({
        match_type: matchType, rules, node_ids: pinnedIds,
      })
      setMatchIds(ids)
    } catch {
      setMatchIds([])
    }
  }, [matchType, rules, pinnedIds])

  useEffect(() => { refreshMatches() }, [refreshMatches])

  const ruleMatchCount = matchIds.length
  const nodeById = useMemo(() => {
    const m = {}
    for (const n of nodes || []) m[n.id] = n
    return m
  }, [nodes])

  function addRule() {
    if (!draftFact) { toast(t('nodeGroups.selectFact'), 'error'); return }
    setRules((r) => [...r, { fact: draftFact, operator: draftOp, value: draftVal }])
    setDraftFact(''); setDraftOp('='); setDraftVal('')
  }
  function removeRule(i) {
    setRules((r) => r.filter((_, idx) => idx !== i))
  }
  function togglePin(id) {
    setPinnedIds((p) => p.includes(id) ? p.filter((x) => x !== id) : [...p, id])
  }

  async function handleCreate() {
    if (!name.trim()) { toast(t('nodeGroups.name') + ' *', 'error'); setStep(1); return }
    setSaving(true)
    try {
      const created = await createNodeGroup({
        name: name.trim(),
        description: description.trim() || undefined,
        parent,
        environment: environment.trim() || 'production',
        is_environment_group: isEnvGroup,
        match_type: matchType,
        rules,
        node_ids: pinnedIds,
      })
      const allSynced = created.wazuh_synced && created.puppet_synced
      const parts = [
        created.wazuh_synced ? 'Wazuh ✓' : 'Wazuh sync failed',
        created.puppet_synced ? 'Puppet ✓' : 'Puppet sync failed',
      ]
      toast(`${t('nodeGroups.created')} — ${parts.join(', ')}`, allSynced ? 'success' : 'warning')
      onCreated()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const canNext1 = name.trim().length > 0

  return (
    <div className="max-w-3xl">
      <button
        onClick={onCancel}
        className="inline-flex items-center gap-1.5 text-[12px] text-gray-500 hover:text-gray-800 mb-4"
      >
        <ArrowLeft size={14} /> {t('nodeGroups.title')}
      </button>

      <h2 className="text-[18px] font-semibold text-gray-900 mb-1">{t('nodeGroups.createGroup')}</h2>
      <p className="text-[12px] text-gray-400 mb-6">{t('nodeGroups.sameEnvNote')}</p>

      <Stepper step={step} labels={[t('nodeGroups.stepDetails'), t('nodeGroups.stepRules'), t('nodeGroups.stepReview')]} />

      <div className="bg-white rounded-xl border border-gray-100 p-6">
        {/* ── STEP 1 ── */}
        {step === 1 && (
          <div className="space-y-4">
            <p className="text-[12px] text-gray-400">{t('nodeGroups.stepDetailsDesc')}</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('nodeGroups.parentName')}</label>
                <select
                  value={parent}
                  onChange={(e) => setParent(e.target.value)}
                  className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand bg-white"
                >
                  {parentOptions.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('nodeGroups.name')} *</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                  placeholder="e.g. web-servers"
                  className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('nodeGroups.environment')}</label>
                <input
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                  className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
                />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={isEnvGroup} onChange={(e) => setIsEnvGroup(e.target.checked)} className="accent-brand" />
                  <span className="text-[12px] text-gray-700">{t('nodeGroups.environmentGroup')}</span>
                </label>
              </div>
            </div>
            {isEnvGroup && (
              <p className="text-[11px] text-gray-400 -mt-1">{t('nodeGroups.environmentGroupHint')}</p>
            )}
            <div>
              <label className="block text-[11px] font-medium text-gray-500 mb-1">{t('nodeGroups.descriptionOptional')}</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 resize-none"
              />
            </div>
          </div>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <div className="space-y-6">
            <p className="text-[12px] text-gray-400">{t('nodeGroups.stepRulesDesc')}</p>

            {/* Dynamic rules */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <GitBranch size={14} className="text-brand" />
                <h4 className="text-[13px] font-semibold text-gray-800">{t('nodeGroups.rulesTitle')}</h4>
              </div>
              <p className="text-[11px] text-gray-400 mb-3">{t('nodeGroups.rulesHint')}</p>
              <div className="flex items-center gap-4 mb-3 text-[12px]">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" checked={matchType === 'all'} onChange={() => setMatchType('all')} className="accent-brand" />
                  {t('nodeGroups.matchAll')}
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="radio" checked={matchType === 'any'} onChange={() => setMatchType('any')} className="accent-brand" />
                  {t('nodeGroups.matchAny')}
                </label>
              </div>

              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="bg-gray-50 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                      <th className="text-left px-3 py-2">{t('nodeGroups.fact')}</th>
                      <th className="text-left px-3 py-2 w-24">{t('nodeGroups.operator')}</th>
                      <th className="text-left px-3 py-2">{t('nodeGroups.value')}</th>
                      <th className="px-3 py-2 w-10" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {rules.map((r, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 text-gray-700">{r.fact}</td>
                        <td className="px-3 py-2 text-gray-700 font-mono">{r.operator}</td>
                        <td className="px-3 py-2 text-gray-700">{r.value || <span className="text-gray-300">—</span>}</td>
                        <td className="px-3 py-2 text-right">
                          <button onClick={() => removeRule(i)} className="p-1 text-gray-400 hover:text-red-500 rounded">
                            <X size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                    {/* draft row */}
                    <tr className="bg-gray-50/40">
                      <td className="px-3 py-2">
                        <select
                          value={draftFact}
                          onChange={(e) => setDraftFact(e.target.value)}
                          className="w-full px-2 py-1.5 text-[12px] border border-gray-200 rounded-md outline-none focus:border-brand bg-white"
                        >
                          <option value="">{t('nodeGroups.selectFact')}</option>
                          {(facts || []).map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={draftOp}
                          onChange={(e) => setDraftOp(e.target.value)}
                          className="w-full px-2 py-1.5 text-[12px] border border-gray-200 rounded-md outline-none focus:border-brand bg-white font-mono"
                        >
                          {OPERATORS.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          value={draftVal}
                          onChange={(e) => setDraftVal(e.target.value)}
                          list="fact-values"
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRule() } }}
                          className="w-full px-2 py-1.5 text-[12px] border border-gray-200 rounded-md outline-none focus:border-brand"
                        />
                        <datalist id="fact-values">
                          {factValues.map((v) => <option key={v} value={v} />)}
                        </datalist>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button onClick={addRule} title={t('nodeGroups.addRule')} className="p-1 text-brand hover:bg-brand/10 rounded">
                          <Plus size={14} />
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {rules.length === 0 && (
                <p className="text-[11px] text-gray-400 italic mt-2">{t('nodeGroups.noRules')}</p>
              )}
            </div>

            {/* Pinned nodes */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Pin size={14} className="text-brand" />
                <h4 className="text-[13px] font-semibold text-gray-800">{t('nodeGroups.pinTitle')}</h4>
              </div>
              <p className="text-[11px] text-gray-400 mb-3">{t('nodeGroups.pinHint')}</p>
              {nodes && nodes.length > 0 ? (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="px-3 py-2 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2">
                    <Search size={12} className="text-gray-400" />
                    <input
                      value={nodeSearch}
                      onChange={(e) => setNodeSearch(e.target.value)}
                      placeholder={t('nodeGroups.nodeName')}
                      className="flex-1 text-[11px] outline-none bg-transparent text-gray-700 placeholder-gray-400"
                    />
                  </div>
                  <div className="max-h-44 overflow-y-auto divide-y divide-gray-50">
                    {filteredNodes.map((n) => (
                      <label key={n.id} className="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-gray-50">
                        <input type="checkbox" checked={pinnedIds.includes(n.id)} onChange={() => togglePin(n.id)} className="accent-brand" />
                        <span className="text-[12px] text-gray-700 font-medium">{n.hostname}</span>
                        {n.ip && <span className="text-[11px] text-gray-400">{n.ip}</span>}
                      </label>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-[12px] text-gray-400 italic">No nodes registered.</p>
              )}
            </div>

            {/* Live match count */}
            <div className="flex items-center gap-2 px-3 py-2 bg-brand/5 border border-brand/15 rounded-lg text-[12px] text-brand">
              <Server size={13} />
              {ruleMatchCount} {t('nodeGroups.matchingNodes').toLowerCase()}
            </div>
          </div>
        )}

        {/* ── STEP 3 ── */}
        {step === 3 && (
          <div className="space-y-5">
            <p className="text-[12px] text-gray-400">{t('nodeGroups.stepReviewDesc')}</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
              <div><dt className="text-gray-400">{t('nodeGroups.name')}</dt><dd className="text-gray-800 font-medium">{name}</dd></div>
              <div><dt className="text-gray-400">{t('nodeGroups.parentName')}</dt><dd className="text-gray-800">{parent}</dd></div>
              <div><dt className="text-gray-400">{t('nodeGroups.environment')}</dt><dd className="text-gray-800">{environment}</dd></div>
              <div><dt className="text-gray-400">{t('nodeGroups.environmentGroup')}</dt><dd className="text-gray-800">{isEnvGroup ? '✓' : '—'}</dd></div>
              <div><dt className="text-gray-400">{t('nodeGroups.rulesTitle')}</dt><dd className="text-gray-800">{rules.length} ({matchType})</dd></div>
              <div><dt className="text-gray-400">{t('nodeGroups.pinned')}</dt><dd className="text-gray-800">{pinnedIds.length}</dd></div>
            </dl>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-[13px] font-semibold text-gray-800">{t('nodeGroups.matchingNodes')}</h4>
                <span className="text-[11px] text-brand font-medium">{matchIds.length} {t('nodeGroups.total').toLowerCase()}</span>
              </div>
              <div className="border border-gray-200 rounded-lg max-h-40 overflow-y-auto divide-y divide-gray-50">
                {matchIds.length === 0 ? (
                  <p className="px-3 py-3 text-[12px] text-gray-400 italic">No nodes match yet.</p>
                ) : (
                  matchIds.map((id) => {
                    const n = nodeById[id]
                    return (
                      <div key={id} className="flex items-center gap-2 px-3 py-2 text-[12px] text-gray-700">
                        <Server size={12} className="text-gray-400" />
                        {n ? n.hostname : id}
                        {n?.ip && <span className="text-[11px] text-gray-400">{n.ip}</span>}
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            <div className="flex items-start gap-2 px-3 py-2 bg-blue-50 border border-blue-100 rounded-lg text-[11px] text-blue-700">
              <CheckCircle size={14} className="flex-shrink-0 mt-0.5" />
              {t('nodeGroups.sameEnvNote')}
            </div>
          </div>
        )}

        {/* ── Footer nav ── */}
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-100">
          <button
            onClick={step === 1 ? onCancel : () => setStep(step - 1)}
            className="inline-flex items-center gap-1.5 border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50"
          >
            <ChevronLeft size={14} /> {step === 1 ? t('common.cancel') : t('nodeGroups.back')}
          </button>
          {step < 3 ? (
            <button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !canNext1}
              className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
            >
              {t('nodeGroups.next')} <ChevronRight size={14} />
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={saving}
              className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 disabled:opacity-50"
            >
              {saving ? <Spinner size={12} /> : <Plus size={12} />}
              {saving ? 'Creating…' : t('nodeGroups.finish')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function NodeGroupsPage() {
  const t = useT()
  const toast = useToast()
  const { data: groups, loading, error, refetch } = useApi(listNodeGroups)
  const { data: nodes } = useApi(listNodes)
  const { data: facts } = useApi(listNodeGroupFacts)

  const [view, setView] = useState('list')
  const [query, setQuery] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const filtered = useMemo(() => {
    if (!groups) return []
    const q = query.toLowerCase()
    return groups.filter((g) =>
      !q || g.name.toLowerCase().includes(q) || (g.description || '').toLowerCase().includes(q))
  }, [groups, query])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteNodeGroup(deleteTarget.id)
      toast(`Group "${deleteTarget.name}" deleted from platform, Wazuh, and Puppet`, 'success')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  if (view === 'wizard') {
    return (
      <div className="p-6">
        <CreateWizard
          groups={groups}
          nodes={nodes}
          facts={facts}
          onCancel={() => setView('list')}
          onCreated={() => { setView('list'); refetch() }}
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-1">
        <h2 className="text-[18px] font-semibold text-gray-900">{t('nodeGroups.title')}</h2>
        <button
          onClick={() => setView('wizard')}
          className="inline-flex items-center gap-1.5 bg-brand text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-brand/90 transition-colors"
        >
          <Plus size={13} />
          {t('nodeGroups.addGroup')}
        </button>
      </div>
      <p className="text-[12px] text-gray-400 mb-5">{t('nodeGroups.subtitle')}</p>

      {/* Filter bar */}
      <div className="relative mb-4 max-w-xs">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter groups…"
          className="w-full pl-8 pr-3 py-2 text-[12px] border border-gray-200 rounded-lg outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 bg-white"
        />
      </div>

      {loading && (
        <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />)}
        </div>
      )}

      {error && (
        <div className="p-4 border border-red-200 bg-red-50 rounded-lg text-[12px] text-red-600">{error}</div>
      )}

      {!loading && !error && (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-gray-400 flex flex-col items-center gap-2">
              <Server size={28} className="text-gray-200" />
              {query ? 'No groups match your filter.' : t('nodeGroups.noGroups')}
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('nodeGroups.name')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('nodeGroups.environment')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('nodeGroups.matchingNodes')}</th>
                  <th className="text-center px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('nodeGroups.wazuhSync')}</th>
                  <th className="text-center px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{t('nodeGroups.puppetSync')}</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((g) => (
                  <tr key={g.id} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-medium text-gray-800">
                      <div className="flex items-center gap-2">
                        <Server size={13} className="text-gray-400 flex-shrink-0" />
                        <span>{g.name}</span>
                        {g.parent && g.parent !== 'All Nodes' && (
                          <span className="text-[10px] text-gray-400">⤷ {g.parent}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{g.environment || 'production'}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {(g.matching_node_ids?.length ?? 0)}
                      {g.rules?.length > 0 && (
                        <span className="ml-1 text-[10px] text-gray-400">({g.rules.length} rule{g.rules.length !== 1 ? 's' : ''})</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center"><span className="inline-flex justify-center"><SyncIcon ok={g.wazuh_synced} /></span></td>
                    <td className="px-4 py-3 text-center"><span className="inline-flex justify-center"><SyncIcon ok={g.puppet_synced} /></span></td>
                    <td className="px-4 py-3 text-gray-400">{relativeTime(g.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => setDeleteTarget(g)}
                          title="Delete group"
                          className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <Modal title="Delete node group?" onClose={() => setDeleteTarget(null)}>
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 bg-red-50 border border-red-100 rounded-lg">
              <XCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-[12px] font-medium text-red-800 mb-0.5">
                  Deleting <span className="font-semibold">"{deleteTarget.name}"</span>
                </p>
                <p className="text-[11px] text-red-600">{t('nodeGroups.deleteConfirm')}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-1.5 bg-red-600 text-white px-3 py-1.5 rounded-lg text-[12px] font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Spinner size={12} /> : <Trash2 size={12} />}
                {deleting ? 'Deleting…' : 'Delete group'}
              </button>
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-[12px] hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
