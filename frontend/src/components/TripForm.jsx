import { useState } from 'react'
import LocationInput from './LocationInput'

const SAMPLE_TRIP = {
  current: { label: 'Chicago, Illinois, US', short: 'Chicago, IL', lat: 41.8781, lng: -87.6298 },
  pickup: { label: 'St. Louis, Missouri, US', short: 'St. Louis, MO', lat: 38.627, lng: -90.1994 },
  dropoff: { label: 'Los Angeles, California, US', short: 'Los Angeles, CA', lat: 34.0522, lng: -118.2437 },
  cycle: '22',
}

function defaultStart() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(6, 0, 0, 0)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T06:00`
}

export default function TripForm({ onSubmit, loading, carrier, setCarrier }) {
  const [current, setCurrent] = useState({ label: '' })
  const [pickup, setPickup] = useState({ label: '' })
  const [dropoff, setDropoff] = useState({ label: '' })
  const [cycle, setCycle] = useState('0')
  const [start, setStart] = useState(defaultStart)
  const [errors, setErrors] = useState({})

  const validate = () => {
    const e = {}
    if ((current.label || '').trim().length < 2) e.current = 'Enter where the truck is now.'
    if ((pickup.label || '').trim().length < 2) e.pickup = 'Enter the pickup location.'
    if ((dropoff.label || '').trim().length < 2) e.dropoff = 'Enter the drop-off location.'
    const c = Number(cycle)
    if (cycle === '' || Number.isNaN(c) || c < 0 || c > 70) e.cycle = 'Use a number of hours from 0 to 70.'
    if (!start) e.start = 'Pick a start date and time.'
    setErrors(e)
    return !Object.keys(e).length
  }

  const submit = (ev) => {
    ev.preventDefault()
    if (!validate()) return
    onSubmit({
      current_location: current,
      pickup_location: pickup,
      dropoff_location: dropoff,
      current_cycle_used: Number(cycle),
      start_time: start,
    })
  }

  const loadSample = () => {
    setCurrent(SAMPLE_TRIP.current)
    setPickup(SAMPLE_TRIP.pickup)
    setDropoff(SAMPLE_TRIP.dropoff)
    setCycle(SAMPLE_TRIP.cycle)
    setErrors({})
  }

  const cycleNum = Math.min(70, Math.max(0, Number(cycle) || 0))

  return (
    <form className="trip-form" onSubmit={submit} noValidate>
      <div className="form-head">
        <h2>Plan a trip</h2>
        <button type="button" className="link-btn" onClick={loadSample}>
          Fill in a sample trip
        </button>
      </div>

      <div className="stops-stack">
        <LocationInput label="Current location" marker="start" value={current} onChange={setCurrent}
          placeholder="City, address or ZIP" error={errors.current} />
        <LocationInput label="Pickup location" marker="pickup" value={pickup} onChange={setPickup}
          placeholder="Where the load is picked up" error={errors.pickup} />
        <LocationInput label="Drop-off location" marker="dropoff" value={dropoff} onChange={setDropoff}
          placeholder="Where the load is delivered" error={errors.dropoff} />
      </div>

      <div className={`field ${errors.cycle ? 'has-error' : ''}`}>
        <label htmlFor="cycle">Current cycle used</label>
        <div className="cycle-row">
          <input id="cycle-range" type="range" min="0" max="70" step="0.25" value={cycleNum}
            aria-label="Current cycle used, hours" onChange={(e) => setCycle(e.target.value)} />
          <div className="num-unit">
            <input id="cycle" type="number" inputMode="decimal" min="0" max="70" step="0.25" value={cycle}
              onChange={(e) => setCycle(e.target.value)} aria-invalid={!!errors.cycle} />
            <span>of 70 h</span>
          </div>
        </div>
        <div className="cycle-meter" aria-hidden="true">
          <span style={{ width: `${(cycleNum / 70) * 100}%` }} />
        </div>
        <p className="hint">{(70 - cycleNum).toFixed(2).replace(/\.?0+$/, '')} hours left in the 70-hour / 8-day cycle.</p>
        {errors.cycle && <p className="field-error">{errors.cycle}</p>}
      </div>

      <div className={`field ${errors.start ? 'has-error' : ''}`}>
        <label htmlFor="start">Departure (home terminal time)</label>
        <input id="start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        {errors.start && <p className="field-error">{errors.start}</p>}
      </div>

      <details className="carrier">
        <summary>Details printed on the log sheets</summary>
        <div className="carrier-grid">
          {[
            ['driver', 'Driver name'],
            ['carrier', 'Carrier'],
            ['office', 'Main office address'],
            ['terminal', 'Home terminal address'],
            ['truck', 'Truck / trailer numbers'],
            ['shipper', 'Shipper & commodity'],
          ].map(([k, l]) => (
            <div className="field" key={k}>
              <label htmlFor={`c-${k}`}>{l}</label>
              <input id={`c-${k}`} type="text" value={carrier[k]}
                onChange={(e) => setCarrier({ ...carrier, [k]: e.target.value })} />
            </div>
          ))}
        </div>
      </details>

      <button className="primary" type="submit" disabled={loading}>
        {loading ? 'Planning route…' : 'Plan route and logs'}
      </button>
      <p className="assumptions">
        Property-carrying driver, 70 h / 8 days. Fuel at least every 1,000 miles, 1 hour for pickup and for drop-off.
      </p>
    </form>
  )
}
