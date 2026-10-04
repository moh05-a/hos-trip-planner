const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error('Could not reach the planning server. Check your connection and try again.')
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (data.errors) {
      const [field, msgs] = Object.entries(data.errors)[0]
      const nice = field.replace(/_/g, ' ').replace('current cycle used', 'Cycle used')
      throw new Error(`${nice.charAt(0).toUpperCase() + nice.slice(1)}: ${[].concat(msgs)[0]}`)
    }
    throw new Error(data.detail || `The server returned an error (${res.status}).`)
  }
  return data
}

export function searchPlaces(q, signal) {
  return request(`/api/geocode/?q=${encodeURIComponent(q)}`, { signal }).then((d) => d.results || [])
}

export function planTrip(body) {
  return request('/api/plan-trip/', { method: 'POST', body: JSON.stringify(body) })
}

/** Free hosting tiers sleep when idle - ping early so the first plan is fast. */
export function wakeServer() {
  fetch(`${API_URL}/api/health/`).catch(() => {})
}
