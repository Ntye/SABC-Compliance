import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Server, Shield, RotateCw, Plus, Trash2, Save, Zap,
  Network, ChevronRight, CheckCircle, XCircle,
} from 'lucide-react'
import {
  getNodeGroup, updateNodeGroup, listNodes, listNodeGroupFacts, runClosedLoop,
} from '../lib/api.js'
import { useApi } from '../hooks/useApi.js'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../context/LangContext.jsx'
import { btn, btnSm, badge } from '../lib/tw.js'
import Spinner from '../components/common/Spinner.jsx'
import StatusDot from '../components/common/StatusDot.jsx'
import EmptyState from '../components/common/EmptyState.jsx'

const OPERATORS = ['=', '!=', '~', '>', '>=', '<', '<=']

function SyncPip({ ok, label }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] ${ok ? 'text-green-700' : 'text-gray-400'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-green-500' : 'bg-gray-300'}`} />
      {label}
    </span>
  )
}

// ── Active response toggle ────────────────────────────────────────────────────
function ActiveResponseCard({ group, onToggled }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const enabled = !!group.active_response_enabled

  async function toggle() {
    setBusy(true)
    try {
      await updateNodeGroup(group.id, { active_response_enabled: !enabled })
      toast(`Active response ${!enabled ? 'enabled' : 'disabled'} for "${group.name}".`, 'success')
      onToggled()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center flex-shrink-0">
            <Zap size={16} className={enabled ? 'text-amber-500' : 'text-gray-300'} />
          </div>
          <div>
            <h3 className="text-[13px] font-semibold text-gray-900">Active response</h3>
            <p className="text-[11px] text-gray-500 mt-0.5 max-w-md">
              When on, a Wazuh alert for any member server drives the closed remediation
              loop (Puppet enforce → re-scan) across the whole group automatically.
            </p>
          </div>
        </div>
        <button
          onClick={toggle}
          disabled={busy}
          role="switch"
          aria-checked={enabled}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${enabled ? 'bg-amber-500' : 'bg-gray-200'} disabled:opacity-50`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <span className={badge(enabled ? 'warning' : 'gray')}>{enabled ? 'Enabled' : 'Disabled'}</span>
        {busy && <Spinner size={13} />}
      </div>
    </div>
  )
}

// ── Rules editor ──────────────────────────────────────────────────────────────
function RulesCard({ group, facts, onSaved }) {
  const toast = useToast()
  const [matchType, setMatchType] = useState(group.match_type || 'all')
  const [rules, setRules] = useState(() => (group.rules || []).map((r) => ({ ...r })))
  const [saving, setSaving] = useState(false)

  // Reset local state whenever the group reloads (e.g. after save/refetch).
  useEffect(() => {
    setMatchType(group.match_type || 'all')
    setRules((group.rules || []).map((r) => ({ ...r })))
  }, [group.id, group.updated_at])

  const factNames = useMemo(() => (facts || []).map((f) => f.name), [facts])
  const valuesFor = (name) => (facts || []).find((f) => f.name === name)?.values || []

  const dirty = useMemo(() => {
    const a = JSON.stringify({ m: group.match_type || 'all', r: group.rules || [] })
    const b = JSON.stringify({ m: matchType, r: rules })
    return a !== b
  }, [group, matchType, rules])

  function addRule() {
    setRules((rs) => [...rs, { fact: factNames[0] || 'os_family', operator: '=', value: '' }])
  }
  function updateRule(i, patch) {
    setRules((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }
  function removeRule(i) {
    setRules((rs) => rs.filter((_, idx) => idx !== i))
  }

  async function save() {
    setSaving(true)
    try {
      await updateNodeGroup(group.id, { match_type: matchType, rules })
      toast('Rules saved.', 'success')
      onSaved()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const isSystem = group.group_type === 'system'

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[13px] font-semibold text-gray-900 flex items-center gap-2">
          <Network size={15} className="text-brand" />Matching rules
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-400">Match</span>
          <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
            {['all', 'any'].map((m) => (
              <button
                key={m}
                onClick={() => setMatchType(m)}
                className={`px-2.5 py-1 text-[11px] font-medium ${matchType === m ? 'bg-brand text-white' : 'bg-white text-gray-500 hover:bg-gray-50'}`}
              >
                {m === 'all' ? 'ALL (AND)' : 'ANY (OR)'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isSystem && (
        <p className="mb-3 text-[11px] text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
          This is a system group. Editing its rules is allowed but may be overwritten when
          the built-in hierarchy is re-seeded.
        </p>
      )}

      {rules.length === 0 ? (
        <p className="text-[12px] text-gray-400 py-2">No rules — the group matches members only by pinned nodes.</p>
      ) : (
        <div className="space-y-2">
          {rules.map((r, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                list={`facts-${i}`}
                value={r.fact}
                onChange={(e) => updateRule(i, { fact: e.target.value })}
                className="w-40 px-2.5 py-1.5 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand"
              />
              <datalist id={`facts-${i}`}>
                {factNames.map((n) => <option key={n} value={n} />)}
              </datalist>
              <select
                value={r.operator}
                onChange={(e) => updateRule(i, { operator: e.target.value })}
                className="px-2 py-1.5 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand"
              >
                {OPERATORS.map((op) => <option key={op} value={op}>{op}</option>)}
              </select>
              <input
                list={`vals-${i}`}
                value={r.value}
                onChange={(e) => updateRule(i, { value: e.target.value })}
                placeholder="value"
                className="flex-1 px-2.5 py-1.5 text-[12px] font-mono border border-gray-200 rounded-lg outline-none focus:border-brand"
              />
              <datalist id={`vals-${i}`}>
                {valuesFor(r.fact).map((v) => <option key={v} value={v} />)}
              </datalist>
              <button onClick={() => removeRule(i)} title="Remove rule"
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mt-4">
        <button onClick={addRule} className={btnSm(false)}><Plus size={12} />Add rule</button>
        <div className="flex-1" />
        <button onClick={save} disabled={!dirty || saving} className={`${btnSm(true)} disabled:opacity-40 disabled:cursor-not-allowed`}>
          {saving ? <Spinner size={12} /> : <Save size={12} />}Save rules
        </button>
      </div>
    </div>
  )
}

// ── Members (attached servers) ────────────────────────────────────────────────
function MembersCard({ group, nodes, navigate }) {
  const memberIds = new Set(group.matching_node_ids || [])
  const members = (nodes || []).filter((n) => memberIds.has(n.id))
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[13px] font-semibold text-gray-900 flex items-center gap-2">
          <Server size={15} className="text-brand" />Attached servers
        </h3>
        <span className="text-[11px] text-gray-400 tabular-nums">{members.length}</span>
      </div>
      {members.length === 0 ? (
        <EmptyState icon={Server} title="No servers attached"
          description="No registered node currently matches this group's rules or is pinned to it." />
      ) : (
        <div className="rounded-xl border border-gray-100 divide-y divide-gray-50">
          {members.map((n) => (
            <button key={n.id} onClick={() => navigate(`/nodes/${n.id}`)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50/60 transition-colors text-left">
              <StatusDot status={n.status} />
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-medium text-gray-800 truncate">{n.hostname}</div>
                <div className="text-[11px] text-gray-400 font-mono truncate">{n.ip}{n.os_name ? ` · ${n.os_name}` : ''}</div>
              </div>
              <SyncPip ok={n.puppet_enrolled} label="Puppet" />
              <SyncPip ok={n.wazuh_enrolled} label="Wazuh" />
              <ChevronRight size={14} className="text-gray-300 flex-shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function NodeGroupDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const t = useT()

  const { data: group, loading, error, refetch } = useApi(() => getNodeGroup(id), { deps: [id] })
  const { data: nodes } = useApi(listNodes)
  const { data: facts } = useApi(listNodeGroupFacts)
  const [looping, setLooping] = useState(false)

  async function handleClosedLoop() {
    const count = group?.matching_node_ids?.length ?? 0
    if (count === 0) { toast('No member servers to remediate.', 'info'); return }
    setLooping(true)
    try {
      const r = await runClosedLoop({ groupId: id, description: `Closed loop on group ${group.name}` })
      toast(`Closed loop: ${r.succeeded}/${r.requested} succeeded` +
        (r.failed ? `, ${r.failed} failed` : '') + (r.skipped ? `, ${r.skipped} skipped` : ''),
        r.failed ? 'error' : 'success')
      refetch()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLooping(false)
    }
  }

  if (loading && !group) return <div className="p-6"><Spinner size={20} /></div>
  if (error || !group) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/node-groups')} className={btn(false)}><ArrowLeft size={14} />Back</button>
        <p className="mt-4 text-[13px] text-red-600">{error || 'Node group not found.'}</p>
      </div>
    )
  }

  const isSystem = group.group_type === 'system'
  const count = group.matching_node_ids?.length ?? 0

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <button onClick={() => navigate('/node-groups')}
        className="flex items-center gap-1.5 text-[12px] text-gray-500 hover:text-gray-800 transition-colors mb-4">
        <ArrowLeft size={14} />Node groups
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div className="flex items-center gap-3 min-w-0">
          {isSystem ? <Shield size={20} className="text-blue-400" /> : <Server size={20} className="text-gray-400" />}
          <div className="min-w-0">
            <h1 className="text-[18px] font-semibold text-gray-900 truncate">{group.name}</h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {isSystem && <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-500 rounded font-medium">system</span>}
              <span className="text-[11px] text-gray-400">env: {group.environment || 'production'}</span>
              {group.parent && group.parent !== 'All Nodes' && (
                <span className="text-[11px] text-gray-400">⤷ {group.parent}</span>
              )}
              <SyncPip ok={group.wazuh_synced} label="Wazuh sync" />
              <SyncPip ok={group.puppet_synced} label="Puppet sync" />
            </div>
          </div>
        </div>
        <button onClick={handleClosedLoop} disabled={looping || count === 0}
          title={count === 0 ? 'No member servers' : 'Enforce with Puppet, then re-scan every member'}
          className={`${btn(true)} disabled:opacity-40 disabled:cursor-not-allowed`}>
          {looping ? <Spinner size={14} /> : <RotateCw size={14} />}Run closed loop
        </button>
      </div>

      <div className="space-y-4">
        <ActiveResponseCard group={group} onToggled={refetch} />
        <MembersCard group={group} nodes={nodes} navigate={navigate} />
        <RulesCard group={group} facts={facts} onSaved={refetch} />
      </div>
    </div>
  )
}
