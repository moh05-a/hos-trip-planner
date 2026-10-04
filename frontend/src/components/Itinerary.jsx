import { Fragment } from 'react'
import { STOP_META, duration, parseLocal } from '../lib/format'

function hoursBetween(a, b) {
  return (new Date(b) - new Date(a)) / 36e5
}

export default function Itinerary({ plan, selected, onSelect }) {
  const { stops } = plan
  return (
    <section className="itinerary" aria-label="Trip itinerary">
      <h2>Itinerary</h2>
      <ol>
        {stops.map((s, i) => {
          const prev = stops[i - 1]
          const p = parseLocal(s.arrive)
          const showDate = !prev || parseLocal(prev.arrive).date !== p.date
          const driveH = prev ? hoursBetween(prev.depart, s.arrive) : 0
          const driveMi = prev ? s.mile - prev.mile : 0
          return (
            <Fragment key={i}>
              {prev && driveMi > 0.05 && (
                <li className="drive-seg">
                  <span className="drive-line" aria-hidden="true" />
                  Drive {duration(driveH)} · {Math.round(driveMi).toLocaleString()} mi
                </li>
              )}
              {showDate && <li className="date-sep">{p.day} {p.date}</li>}
              <li className={`stop ${selected === i ? 'is-selected' : ''}`}>
                <button type="button" onClick={() => onSelect(i)}>
                  <span className={`pin pin-${s.type} ${['start', 'pickup', 'dropoff'].includes(s.type) ? 'pin-major' : ''}`}>
                    <span>{STOP_META[s.type]?.glyph}</span>
                  </span>
                  <span className="stop-body">
                    <span className="stop-top">
                      <strong>{s.title}</strong>
                      <time>{p.time}</time>
                    </span>
                    <span className="stop-place">{s.short}</span>
                    {s.duration_hr > 0 && (
                      <span className="stop-meta">
                        {duration(s.duration_hr)} {s.type === 'fuel' || s.type === 'pickup' || s.type === 'dropoff' ? 'on duty' : s.type === 'rest' ? 'in sleeper berth' : 'off duty'}
                        {' '}· until {parseLocal(s.depart).time}
                        {parseLocal(s.depart).date !== p.date ? ` ${parseLocal(s.depart).date}` : ''}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            </Fragment>
          )
        })}
      </ol>
    </section>
  )
}
