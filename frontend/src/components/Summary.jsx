import { duration, miles, whenLabel } from '../lib/format'

export default function Summary({ plan }) {
  const s = plan.summary
  const items = [
    { k: 'Distance', v: `${miles(s.total_miles)} mi`, sub: `${miles(s.leg_miles[0])} to pickup + ${miles(s.leg_miles[1])} loaded` },
    { k: 'Driving time', v: duration(s.driving_hours), sub: `${duration(s.on_duty_hours)} on duty in total` },
    { k: 'Arrives', v: whenLabel(s.end), sub: `${duration(s.trip_hours)} after departure` },
    { k: 'Stops', v: `${s.fuel_stops} fuel, ${s.rest_breaks + s.overnight_rests + s.restarts} rest`,
      sub: [s.overnight_rests && `${s.overnight_rests} × 10-hr`, s.rest_breaks && `${s.rest_breaks} × 30-min`, s.restarts && `${s.restarts} × 34-hr restart`].filter(Boolean).join(', ') || 'No rest needed' },
    { k: 'Cycle after trip', v: `${s.cycle_used_end.toFixed(1).replace(/\.0$/, '')} / 70 h`, sub: `${(70 - s.cycle_used_end).toFixed(1).replace(/\.0$/, '')} h available` },
  ]
  return (
    <dl className="summary">
      {items.map((it) => (
        <div key={it.k}>
          <dt>{it.k}</dt>
          <dd>{it.v}</dd>
          <dd className="sub">{it.sub}</dd>
        </div>
      ))}
    </dl>
  )
}
