import { forwardRef } from 'react'
import { STATUS_ORDER, hhmm, miles as fmtMiles } from '../lib/format'

/*
 * One Driver's Daily Log, drawn to match the FMCSA paper form:
 * printed parts in black, everything the driver "fills in" in blue ink.
 */
const VB_W = 1080
const X0 = 168 // grid left
const HW = 34 // px per hour
const X1 = X0 + 24 * HW // grid right (984)
const ROW_H = 34
const GRID_TOP = 318
const HEAD_H = 34
const ROWS_TOP = GRID_TOP + HEAD_H
const GRID_BOTTOM = ROWS_TOP + ROW_H * 4
const REMARK_TOP = GRID_BOTTOM + 30
const REMARK_H = 228
const SHIP_TOP = REMARK_TOP + REMARK_H + 8
const RECAP_TOP = SHIP_TOP + 156
const VB_H = RECAP_TOP + 168

const ROW_LABELS = ['1. Off Duty', '2. Sleeper Berth', '3. Driving', '4. On Duty (not driving)']
const KIND_WORD = {
  drive: 'driving', pickup: 'pickup', dropoff: 'drop-off', fuel: 'fuel', break: '30m break',
  rest: '10h rest', restart: '34h restart', off: 'off duty',
}

const x = (h) => X0 + h * HW
const rowY = (status) => ROWS_TOP + STATUS_ORDER.indexOf(status) * ROW_H + ROW_H / 2

function hourLabel(i) {
  if (i === 0 || i === 24) return []
  if (i === 12) return ['Noon']
  return [String(i > 12 ? i - 12 : i)]
}

function Field({ x: fx, y, w, label, value, align = 'start', size = 20 }) {
  return (
    <g>
      <line x1={fx} x2={fx + w} y1={y} y2={y} className="f-line" />
      {value != null && value !== '' && (
        <text x={align === 'middle' ? fx + w / 2 : fx + 6} y={y - 6} textAnchor={align} className="ink" fontSize={size}>
          {value}
        </text>
      )}
      {label && (
        <text x={fx + w / 2} y={y + 15} textAnchor="middle" className="f-small">{label}</text>
      )}
    </g>
  )
}

function Grid() {
  const ticks = []
  for (let r = 0; r < 4; r++) {
    const top = ROWS_TOP + r * ROW_H
    for (let h = 0; h < 24; h++) {
      for (let q = 1; q < 4; q++) {
        const len = q === 2 ? ROW_H * 0.55 : ROW_H * 0.3
        const tx = x(h + q / 4)
        ticks.push(<line key={`${r}-${h}-${q}`} x1={tx} x2={tx} y1={top} y2={top + len} className="g-tick" />)
      }
    }
  }
  return (
    <g>
      {/* header band with hour numbers */}
      <rect x={X0} y={GRID_TOP} width={24 * HW} height={HEAD_H} className="g-head" />
      {Array.from({ length: 25 }, (_, i) => {
        const lines = hourLabel(i)
        return (
          <text key={i} x={x(i)} y={GRID_TOP + 22} textAnchor="middle" className="g-hour">{lines[0]}</text>
        )
      })}
      {[0, 24].map((i) => (
        <text key={`mid${i}`} x={x(i)} y={GRID_TOP - 6} textAnchor="middle" className="f-colhead">Midnight</text>
      ))}
      {/* rows */}
      {ROW_LABELS.map((l, r) => (
        <g key={l}>
          <rect x={X0} y={ROWS_TOP + r * ROW_H} width={24 * HW} height={ROW_H} className="g-row" />
          <text x={X0 - 8} y={ROWS_TOP + r * ROW_H + ROW_H / 2 + 5} textAnchor="end" className="f-label">
            {l.length > 18 ? <><tspan x={X0 - 8} dy="-6">4. On Duty</tspan><tspan x={X0 - 8} dy="13">(not driving)</tspan></> : l}
          </text>
        </g>
      ))}
      {Array.from({ length: 25 }, (_, i) => (
        <line key={i} x1={x(i)} x2={x(i)} y1={GRID_TOP + (i % 24 === 0 ? 0 : HEAD_H - 6)} y2={GRID_BOTTOM}
          className={i % 12 === 0 ? 'g-hour-line strong' : 'g-hour-line'} />
      ))}
      {ticks}
      <rect x={X0} y={GRID_TOP} width={24 * HW} height={GRID_BOTTOM - GRID_TOP} className="g-frame" />
      {/* totals column */}
      <text x={X1 + 46} y={GRID_TOP + 14} textAnchor="middle" className="f-colhead">Total</text>
      <text x={X1 + 46} y={GRID_TOP + 26} textAnchor="middle" className="f-colhead">Hours</text>
      {ROW_LABELS.map((l, r) => (
        <line key={l} x1={X1 + 14} x2={X1 + 80} y1={ROWS_TOP + (r + 1) * ROW_H - 4} y2={ROWS_TOP + (r + 1) * ROW_H - 4}
          className="f-line" />
      ))}
      <line x1={X1 + 14} x2={X1 + 80} y1={GRID_BOTTOM + 20} y2={GRID_BOTTOM + 20} className="f-line" />
      <line x1={X1 + 14} x2={X1 + 80} y1={GRID_BOTTOM + 23} y2={GRID_BOTTOM + 23} className="f-line" />
    </g>
  )
}

function DutyLine({ segments }) {
  // one continuous path: horizontal in each status row, vertical at every change
  let d = ''
  segments.forEach((s, i) => {
    const y = rowY(s.status)
    if (i === 0) d += `M ${x(s.start)} ${y}`
    else d += ` L ${x(s.start)} ${y}`
    d += ` L ${x(s.end)} ${y}`
  })
  return <path d={d} className="duty-line" />
}

function Remarks({ remarks, segments }) {
  // brackets under on-duty (not driving) periods, as drivers do on paper
  const brackets = segments.filter((s) => s.status === 'ON')
  return (
    <g>
      {brackets.map((s, i) => (
        <path key={`b${i}`} className="ink-stroke"
          d={`M ${x(s.start)} ${GRID_BOTTOM + 4} L ${x(s.start)} ${GRID_BOTTOM + 14} L ${x(s.end)} ${GRID_BOTTOM + 14} L ${x(s.end)} ${GRID_BOTTOM + 4}`} />
      ))}
      {remarks.map((r, i) => {
        const rx = x(r.time)
        const place = r.location.length > 24 ? `${r.location.slice(0, 22)}…` : r.location
        const label = `${place} (${KIND_WORD[r.kind] || r.kind})`
        return (
          <g key={i}>
            <line x1={rx} x2={rx} y1={GRID_BOTTOM + 2} y2={REMARK_TOP + 2} className="ink-stroke thin" />
            <text transform={`translate(${rx + 3} ${REMARK_TOP + 8}) rotate(66)`} className="ink remark" fontSize="13">
              {label}
            </text>
          </g>
        )
      })}
    </g>
  )
}

const LogSheet = forwardRef(function LogSheet({ log, totalDays, carrier, plan }, ref) {
  const [yy, mm, dd] = log.date.split('-')
  const totalSum = STATUS_ORDER.reduce((a, k) => a + log.totals[k], 0)
  const odometer = plan.logs.slice(0, log.day).reduce((a, l) => a + l.miles, 0)
  return (
    <svg ref={ref} viewBox={`0 0 ${VB_W} ${VB_H}`} className="log-svg" role="img"
      aria-label={`Driver's daily log for ${log.date}, day ${log.day} of ${totalDays}`}
      xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width={VB_W} height={VB_H} className="paper" />

      {/* ---------------- header ---------------- */}
      <text x="40" y="58" className="f-title">Drivers Daily Log</text>
      <text x="40" y="78" className="f-small">(24 hours)</text>
      <Field x={320} y={58} w={78} label="(month)" value={mm} align="middle" />
      <text x={404} y={56} className="f-label">/</text>
      <Field x={416} y={58} w={78} label="(day)" value={dd} align="middle" />
      <text x={500} y={56} className="f-label">/</text>
      <Field x={512} y={58} w={96} label="(year)" value={yy} align="middle" />
      <text x={652} y={36} className="f-small">Original - File at home terminal.</text>
      <text x={652} y={52} className="f-small">Duplicate - Driver retains in his/her possession for 8 days.</text>
      <text x={652} y={76} className="f-small">Sheet {log.day} of {totalDays}</text>

      <text x="40" y="122" className="f-label">From:</text>
      <Field x={92} y={124} w={380} value={log.from_location} />
      <text x="520" y="122" className="f-label">To:</text>
      <Field x={552} y={124} w={480} value={log.to_location} />

      <rect x="40" y="150" width="190" height="56" className="f-box" />
      <text x="135" y="186" textAnchor="middle" className="ink" fontSize="24">{fmtMiles(log.miles)}</text>
      <text x="135" y="222" textAnchor="middle" className="f-small">Total Miles Driving Today</text>
      <rect x="246" y="150" width="190" height="56" className="f-box" />
      <text x="341" y="186" textAnchor="middle" className="ink" fontSize="24">{fmtMiles(odometer)}</text>
      <text x="341" y="222" textAnchor="middle" className="f-small">Total Mileage (trip to date)</text>
      <Field x={40} y={274} w={396} value={carrier.truck} label="Truck/Tractor and Trailer Numbers or License Plate(s)/State (show each unit)" size={18} />

      <Field x={480} y={168} w={552} value={carrier.carrier} label="Name of Carrier or Carriers" align="middle" size={19} />
      <Field x={480} y={218} w={552} value={carrier.office} label="Main Office Address" align="middle" size={19} />
      <Field x={480} y={268} w={552} value={carrier.terminal} label="Home Terminal Address" align="middle" size={19} />

      {/* ---------------- grid ---------------- */}
      <Grid />
      <DutyLine segments={log.segments} />
      {STATUS_ORDER.map((k, r) => (
        <text key={k} x={X1 + 47} y={ROWS_TOP + (r + 1) * ROW_H - 9} textAnchor="middle" className="ink" fontSize="17">
          {hhmm(log.totals[k])}
        </text>
      ))}
      <text x={X1 + 47} y={GRID_BOTTOM + 16} textAnchor="middle" className="ink" fontSize="17">{hhmm(totalSum)}</text>

      {/* ---------------- remarks ---------------- */}
      <text x="40" y={GRID_BOTTOM + 22} className="f-section">Remarks</text>
      <line x1="40" x2="40" y1={GRID_BOTTOM + 30} y2={SHIP_TOP + 136} className="f-rule" />
      <Remarks remarks={log.remarks} segments={log.segments} />

      {/* ---------------- shipping ---------------- */}
      <text x="56" y={SHIP_TOP + 6} className="f-label strong">Shipping</text>
      <text x="56" y={SHIP_TOP + 24} className="f-label strong">Documents:</text>
      <Field x={56} y={SHIP_TOP + 62} w={250} value={plan.locations ? `BOL-${log.date.replace(/-/g, '')}` : ''} />
      <text x="56" y={SHIP_TOP + 78} className="f-small">DVL or Manifest No. or</text>
      <Field x={56} y={SHIP_TOP + 112} w={250} value={carrier.shipper} size={16} />
      <text x="56" y={SHIP_TOP + 128} className="f-small">Shipper &amp; Commodity</text>
      <text x={X0 + 12 * HW} y={SHIP_TOP + 92} textAnchor="middle" className="f-small">
        Enter name of place you reported and where released from work and when and where each change of duty occurred.
      </text>
      <text x={X0 + 12 * HW} y={SHIP_TOP + 108} textAnchor="middle" className="f-small">Use time standard of home terminal.</text>

      {/* ---------------- recap ---------------- */}
      <line x1="40" x2={VB_W - 40} y1={RECAP_TOP - 6} y2={RECAP_TOP - 6} className="f-rule" />
      <text x="40" y={RECAP_TOP + 16} className="f-label strong">Recap:</text>
      <text x="40" y={RECAP_TOP + 32} className="f-small">Complete at end of day</text>

      <text x="200" y={RECAP_TOP + 16} className="f-small">On duty hours today,</text>
      <text x="200" y={RECAP_TOP + 30} className="f-small">Total lines 3 &amp; 4</text>
      <Field x={200} y={RECAP_TOP + 70} w={110} value={hhmm(log.recap.on_duty_today)} align="middle" />

      <text x="350" y={RECAP_TOP + 16} className="f-label strong">70 Hour / 8 Day Drivers</text>
      {[
        ['A.', 'Total hours on duty', 'last 7 days including today', log.recap.cycle_total],
        ['B.', 'Total hours available', 'tomorrow, 70 hr minus A*', log.recap.available_tomorrow],
        ['C.', 'Total hours on duty', 'last 8 days including today', log.recap.cycle_total],
      ].map(([k, l1, l2, v], i) => {
        const cx = 350 + i * 200
        return (
          <g key={k}>
            <text x={cx} y={RECAP_TOP + 40} className="f-label strong">{k}</text>
            <text x={cx + 20} y={RECAP_TOP + 40} className="f-small">{l1}</text>
            <text x={cx + 20} y={RECAP_TOP + 54} className="f-small">{l2}</text>
            <Field x={cx + 20} y={RECAP_TOP + 96} w={130} value={hhmm(v)} align="middle" />
          </g>
        )
      })}
      <text x="350" y={RECAP_TOP + 130} className="f-small">
        *If you took 34 consecutive hours off duty you have 70 hours available.
      </text>
      <text x="350" y={RECAP_TOP + 146} className="f-small muted">
        A and C include the {plan.summary.cycle_used_start} h already used when the trip began.
      </text>
      <Field x={VB_W - 280} y={RECAP_TOP + 130} w={240} value={carrier.driver} label="Driver's signature" align="middle" size={20} />
    </svg>
  )
})

export default LogSheet
