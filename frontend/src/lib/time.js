// Backend stores UTC datetimes without a timezone suffix. Append 'Z' so the
// browser always parses them as UTC rather than local time — the caller then
// renders them in the viewer's local timezone (toLocaleString, relative deltas).
export function utcDate(iso) {
  if (!iso) return null
  return new Date(/[Zz]|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z')
}
