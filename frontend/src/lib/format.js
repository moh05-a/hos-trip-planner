export const STATUS = {
  OFF: { label: 'Off duty', line: '1. Off Duty', color: 'var(--st-off)' },
  SB: { label: 'Sleeper berth', line: '2. Sleeper Berth', color: 'var(--st-sb)' },
  D: { label: 'Driving', line: '3. Driving', color: 'var(--st-d)' },
  ON: { label: 'On duty (not driving)', line: '4. On Duty (not driving)', color: 'var(--st-on)' },
}
export const STATUS_ORDER = ['OFF', 'SB', 'D', 'ON']

export const STOP_META = {
  start: { glyph: 'A', name: 'Start' },
  pickup: { glyph: 'P', name: 'Pickup' },
  dropoff: { glyph: 'D', name: 'Drop-off' },
  fuel: { glyph: 'F', name: 'Fuel stop' },
  break: { glyph: '½', name: '30-min break' },
  rest: { glyph: 'Z', name: '10-hr rest' },
  restart: { glyph: 'R', name: '34-hr restart' },
}

/** 7.25 -> "7:15" (hours since midnight -> clock) */
export function clock(hours) {
  let mins = Math.round(hours * 60)
  if (mins >= 24 * 60) mins = 24 * 60
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** 1.5 -> "1h 30m" */
export function duration(hours) {
  const mins = Math.round(hours * 60)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (!h) return `${m}m`
  if (!m) return `${h}h`
  return `${h}h ${m}m`
}

/** 13.25 -> "13:15" for the totals column */
export function hhmm(hours) {
  const mins = Math.round(hours * 60)
  return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-10-05T06:00" -> { day: "Mon", date: "Oct 5", time: "06:00" } */
export function parseLocal(iso) {
  const [d, t = '00:00'] = iso.split('T')
  const [y, mo, da] = d.split('-').map(Number)
  const dt = new Date(y, mo - 1, da)
  return { day: DAYS[dt.getDay()], date: `${MONTHS[mo - 1]} ${da}`, time: t.slice(0, 5), y, mo, da }
}

export function whenLabel(iso) {
  const p = parseLocal(iso)
  return `${p.day} ${p.date}, ${p.time}`
}

export const miles = (n) => Math.round(n).toLocaleString('en-US')
