import { useEffect, useRef, useState } from 'react'
import TripForm from './components/TripForm'
import RouteMap from './components/RouteMap'
import Itinerary from './components/Itinerary'
import Summary from './components/Summary'
import LogSheets from './components/LogSheets'
import { planTrip, wakeServer } from './lib/api'

const DEFAULT_CARRIER = {
  driver: 'Alex Driver',
  carrier: 'Spotter Freight Lines',
  office: '100 Main St, Chicago, IL',
  terminal: '100 Main St, Chicago, IL',
  truck: 'Tractor 2417 / Trailer 5530 (IL)',
  shipper: 'Acme Foods, dry groceries',
}

export default function App() {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [carrier, setCarrier] = useState(DEFAULT_CARRIER)
  const [slow, setSlow] = useState(false)
  const resultsRef = useRef(null)

  useEffect(() => { wakeServer() }, [])

  const submit = async (body) => {
    setLoading(true)
    setError('')
    setSelected(null)
    setSlow(false)
    const slowTimer = setTimeout(() => setSlow(true), 7000)
    try {
      const data = await planTrip(body)
      setPlan(data)
      if (window.matchMedia('(max-width: 1100px)').matches) {
        setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      clearTimeout(slowTimer)
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg className="shield" viewBox="0 0 40 44" aria-hidden="true">
            <path d="M3 4c6 2 11 2 17-2 6 4 11 4 17 2 3 14 2 28-17 38C1 32 0 18 3 4z" fill="#F2B705" stroke="#fff" strokeWidth="2" />
            <text x="20" y="28" textAnchor="middle" fontSize="15" fontWeight="700" fill="#1D2530">70</text>
          </svg>
          <div>
            <h1>HOS Trip Planner</h1>
            <p>Route, required stops and daily logs for property-carrying drivers</p>
          </div>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <TripForm onSubmit={submit} loading={loading} carrier={carrier} setCarrier={setCarrier} />
          {error && <div className="alert" role="alert">{error}</div>}
          {plan && <Itinerary plan={plan} selected={selected} onSelect={setSelected} />}
        </aside>

        <main className="main" ref={resultsRef}>
          <div className="map-area">
            <RouteMap plan={plan} selected={selected} onSelect={setSelected} />
            {!plan && !loading && (
              <div className="map-empty">
                <h2>Where is the load going?</h2>
                <p>Enter the truck's location, the pickup and the drop-off. You'll get the route with every
                  fuel stop and required rest, plus a filled-in log sheet for each day on the road.</p>
              </div>
            )}
            {loading && (
              <div className="map-loading" role="status">
                <span className="road" aria-hidden="true"><span /></span>
                Finding the route and scheduling breaks…
                {slow && <small className="slow">The server was asleep and is starting up. This can take up to a minute the first time.</small>}
              </div>
            )}
          </div>

          {plan && (
            <>
              {plan.warnings?.length > 0 && (
                <div className="notice">{plan.warnings[0].split(' - ')[0]}. Mileage is approximate.</div>
              )}
              <Summary plan={plan} />
              <LogSheets key={plan.summary.start + plan.summary.total_miles} plan={plan} carrier={carrier} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}
