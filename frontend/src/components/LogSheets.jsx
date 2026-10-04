import { useState } from 'react'
import LogSheet from './LogSheet'
import { STATUS, STATUS_ORDER, duration, parseLocal } from '../lib/format'

export default function LogSheets({ plan, carrier }) {
  const [day, setDay] = useState(0)
  const logs = plan.logs
  const current = logs[Math.min(day, logs.length - 1)]

  return (
    <section className="logs" aria-label="Daily log sheets">
      <div className="logs-head">
        <div>
          <h2>Daily log sheets</h2>
          <p className="logs-sub">
            {logs.length === 1 ? 'One sheet' : `${logs.length} sheets`}, one for each calendar day of the trip.
          </p>
        </div>
        <button type="button" className="secondary" onClick={() => window.print()}>
          Print or save all as PDF
        </button>
      </div>

      <div className="day-tabs" role="tablist" aria-label="Log sheet day">
        {logs.map((l, i) => {
          const p = parseLocal(`${l.date}T00:00`)
          return (
            <button key={l.date} role="tab" type="button" aria-selected={i === day}
              className={i === day ? 'on' : ''} onClick={() => setDay(i)}>
              <span className="tab-day">Day {l.day}</span>
              <span className="tab-date">{p.day} {p.date}</span>
              <span className="tab-mi">{Math.round(l.miles).toLocaleString()} mi</span>
            </button>
          )
        })}
      </div>

      <div className="day-totals" aria-label="Hours by duty status">
        {STATUS_ORDER.map((k) => (
          <div key={k} className={`dt dt-${k}`}>
            <span className="swatch" />
            <span className="dt-label">{STATUS[k].label}</span>
            <span className="dt-val">{duration(current.totals[k]) || '0m'}</span>
          </div>
        ))}
      </div>

      <p className="sheet-hint screen-only">Swipe sideways to see the whole sheet.</p>
      <div className="sheet-frame screen-only" role="tabpanel">
        <LogSheet log={current} totalDays={logs.length} carrier={carrier} plan={plan} />
      </div>

      {/* every sheet, only rendered for printing */}
      <div className="print-only">
        {logs.map((l) => (
          <div className="print-page" key={l.date}>
            <LogSheet log={l} totalDays={logs.length} carrier={carrier} plan={plan} />
          </div>
        ))}
      </div>
    </section>
  )
}
