import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { STOP_META, duration, whenLabel } from '../lib/format'

const US_CENTER = [39.5, -98.35]

function icon(type, n) {
  const meta = STOP_META[type] || { glyph: '•' }
  const major = type === 'start' || type === 'pickup' || type === 'dropoff'
  return L.divIcon({
    className: '',
    html: `<div class="pin pin-${type} ${major ? 'pin-major' : ''}"><span>${meta.glyph}</span>${n ? `<i>${n}</i>` : ''}</div>`,
    iconSize: major ? [34, 34] : [26, 26],
    iconAnchor: major ? [17, 17] : [13, 13],
    popupAnchor: [0, -14],
  })
}

function FitBounds({ plan }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const pts = plan.route.legs.flatMap((l) => l.geometry)
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [36, 36] })
  }, [plan, map])
  return null
}

function FlyTo({ stop }) {
  const map = useMap()
  useEffect(() => {
    if (stop) map.flyTo([stop.lat, stop.lng], Math.max(map.getZoom(), 9), { duration: 0.8 })
  }, [stop, map])
  return null
}

export default function RouteMap({ plan, selected, onSelect }) {
  const markerRefs = useRef({})

  // group stops at (almost) the same point so markers don't hide each other
  const stops = useMemo(() => (plan ? plan.stops.map((s, i) => ({ ...s, idx: i })) : []), [plan])

  useEffect(() => {
    if (selected != null) markerRefs.current[selected]?.openPopup()
  }, [selected])

  return (
    <div className="map-shell">
      <MapContainer center={US_CENTER} zoom={4} scrollWheelZoom className="map" zoomControl>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        {plan && (
          <>
            <FitBounds plan={plan} />
            {plan.route.legs.map((leg, i) => (
              <Polyline key={`casing-${i}`} positions={leg.geometry}
                pathOptions={{ color: '#1D2530', weight: 8, opacity: 0.85 }} />
            ))}
            {plan.route.legs.map((leg, i) => (
              <Polyline key={`leg-${i}`} positions={leg.geometry}
                pathOptions={i === 0
                  ? { color: '#F2B705', weight: 4, dashArray: '8 8' }
                  : { color: '#F2B705', weight: 4 }} />
            ))}
            {stops.map((s) => (
              <Marker
                key={s.idx}
                position={[s.lat, s.lng]}
                icon={icon(s.type)}
                zIndexOffset={['start', 'pickup', 'dropoff'].includes(s.type) ? 1000 : 0}
                ref={(r) => { markerRefs.current[s.idx] = r }}
                eventHandlers={{ click: () => onSelect?.(s.idx) }}
              >
                <Popup>
                  <div className="pop">
                    <strong>{s.title}</strong>
                    <span className="pop-place">{s.short}</span>
                    <span>{whenLabel(s.arrive)}{s.duration_hr ? ` · ${duration(s.duration_hr)}` : ''}</span>
                    <span className="pop-note">{s.note}</span>
                    <span className="pop-mile">Mile {Math.round(s.mile).toLocaleString()}</span>
                  </div>
                </Popup>
              </Marker>
            ))}
            <FlyTo stop={selected != null ? stops[selected] : null} />
          </>
        )}
      </MapContainer>
      <ul className="map-legend" aria-label="Map legend">
        <li><span className="leg-line dashed" />To pickup</li>
        <li><span className="leg-line" />Loaded</li>
        <li><span className="pin pin-fuel mini"><span>F</span></span>Fuel</li>
        <li><span className="pin pin-break mini"><span>½</span></span>30-min break</li>
        <li><span className="pin pin-rest mini"><span>Z</span></span>10-hr rest</li>
        <li><span className="pin pin-restart mini"><span>R</span></span>34-hr restart</li>
      </ul>
    </div>
  )
}
