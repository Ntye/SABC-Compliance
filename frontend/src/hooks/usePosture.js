import { useCallback, useEffect, useState } from 'react'
import { getComplianceSummary, listDetectionEvents } from '../lib/api.js'

// The report that represents a node's compliance (a real scan first, then a
// CIS-over-SSH run, then anything that isn't a bare puppet run).
// Lifecycle status of a detection event. A change that has been corrected
// (remediation succeeded) or that was suppressed as sanctioned is NOT an open
// alert; only a genuine, unresolved change — or one whose remediation failed —
// counts against the "active alerts" figure.
export function eventStatus(e) {
  if (e.suppressed) return 'suppressed'
  const o = e.remediation_outcome
  if (o === 'success' || o === 'skipped') return 'resolved'
  if (o === 'pending') return 'remediating'
  if (o === 'failed') return 'failed'
  return 'active'
}

export function isActiveAlert(e) {
  const s = eventStatus(e)
  return s === 'active' || s === 'failed'
}

export function primaryReport(node) {
  const reports = node.reports || []
  return (
    reports.find((r) => r.source === 'scan') ||
    reports.find((r) => r.source === 'cis-ssh') ||
    reports.find((r) => r.source !== 'puppet') ||
    null
  )
}

function bucketAverages(pairs) {
  // pairs: [{ key, score }] → [{ key, score, count }] averaged, sorted desc.
  const acc = {}
  for (const { key, score } of pairs) {
    const k = key || '—'
    acc[k] = acc[k] || { sum: 0, count: 0 }
    acc[k].sum += score
    acc[k].count += 1
  }
  return Object.entries(acc)
    .map(([key, v]) => ({ key, score: Math.round(v.sum / v.count), count: v.count }))
    .sort((a, b) => b.score - a.score)
}

// Fleet posture derived from the compliance summary + detection feed. Shared by
// the top bar (global score / nodes / active alerts) and the dashboard.
export function usePosture() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(async () => {
    try {
      const [nodes, events] = await Promise.all([
        getComplianceSummary(),
        listDetectionEvents({ limit: 300 }).catch(() => []),
      ])
      const list = Array.isArray(nodes) ? nodes : []
      const scanned = []
      let passed = 0, failed = 0, skipped = 0, critical = 0, scoreSum = 0
      let lastSweep = null
      const tierPairs = [], osPairs = [], fwPairs = []
      for (const node of list) {
        const r = primaryReport(node)
        if (!r) continue
        scanned.push({ node, report: r })
        const score = r.score || 0
        passed += r.passed_checks || 0
        failed += r.failed_checks || 0
        skipped += r.skipped_checks || 0
        critical += r.severity_counts?.high || 0
        scoreSum += score
        if (r.collected_at && (!lastSweep || r.collected_at > lastSweep)) lastSweep = r.collected_at
        tierPairs.push({ key: node.tier_name || r.tier_name, score })
        osPairs.push({ key: node.os_family || r.os_family, score })
        fwPairs.push({ key: r.profile || r.framework, score })
      }
      const globalScore = scanned.length ? Math.round(scoreSum / scanned.length) : 0
      const outOfCompliance = scanned.filter(({ report }) => (report.score || 0) < 90).length
      const activeAlerts = (Array.isArray(events) ? events : []).filter(isActiveAlert).length
      const validationOnly = list.filter((n) => n.enforcement_enabled === false).length

      setState({
        loading: false, error: null,
        data: {
          totalNodes: list.length,
          scanned: scanned.length,
          globalScore, outOfCompliance, activeAlerts, validationOnly,
          passed, failed, skipped, critical, lastSweep,
          byTier: bucketAverages(tierPairs),
          byOs: bucketAverages(osPairs),
          byFramework: bucketAverages(fwPairs),
          scoreByNode: scanned
            .map(({ node, report }) => ({ name: node.hostname, score: report.score || 0 }))
            .sort((a, b) => a.score - b.score),
        },
      })
    } catch (err) {
      setState({ loading: false, error: err.message || 'Failed to load posture', data: null })
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 60000) // refresh posture every minute
    return () => clearInterval(id)
  }, [load])

  return { ...state, refetch: load }
}
