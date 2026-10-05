import { useEffect, useId, useRef, useState } from 'react'
import { searchPlaces } from '../lib/api'

const MIN_CHARS = 2

/**
 * Text input with place suggestions. `value` is { label, lat?, lng?, short? }.
 * Typing clears the coordinates; picking a suggestion sets them.
 */
export default function LocationInput({ label, marker, value, onChange, placeholder, error }) {
  const [open, setOpen] = useState(false)
  // results remember the text they were found for, so stale ones can be hidden
  const [found, setFound] = useState({ q: '', items: [] })
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const inputId = useId()
  const boxRef = useRef(null)
  const sent = useRef(0)
  const shown = useRef(0)
  const lastSentAt = useRef(0)
  const query = value?.label || ''
  const picked = value?.lat != null
  const typed = query.trim().toLowerCase()
  // keep showing results for an earlier prefix ("chi") while the search for "chicago" is on its way
  const suggestions = picked || typed.length < MIN_CHARS || !typed.startsWith(found.q) ? [] : found.items

  useEffect(() => {
    const q = query.trim()
    if (picked || q.length < MIN_CHARS) return
    // wait for a 200 ms pause, but never more than 400 ms after the last request,
    // so suggestions keep coming while someone types without stopping
    const wait = Math.max(0, Math.min(200, lastSentAt.current + 400 - Date.now()))
    const t = setTimeout(async () => {
      // requests are not aborted when the user keeps typing: the geocoder takes a second
      // or two, and an answer for a shorter prefix is still worth showing
      lastSentAt.current = Date.now()
      const n = ++sent.current
      setLoading(true)
      try {
        const items = await searchPlaces(q)
        if (n > shown.current) {
          shown.current = n
          setFound({ q: q.toLowerCase(), items })
          setActive(items.length ? 0 : -1)
        }
      } catch {
        /* suggestions are optional - the server geocodes free text too */
      } finally {
        if (n === sent.current) setLoading(false)
      }
    }, wait)
    return () => clearTimeout(t)
  }, [query, picked])

  useEffect(() => {
    const close = (e) => boxRef.current && !boxRef.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const choose = (r) => {
    onChange(r)
    setOpen(false)
  }

  const onKey = (e) => {
    if (!open || !suggestions.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => (a + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a - 1 + suggestions.length) % suggestions.length)
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault()
      choose(suggestions[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={`field loc ${error ? 'has-error' : ''}`} ref={boxRef}>
      <label htmlFor={inputId}>{label}</label>
      <div className="loc-wrap">
        <span className={`loc-marker m-${marker}`} aria-hidden="true">{marker === 'start' ? 'A' : marker === 'pickup' ? 'P' : 'D'}</span>
        <input
          id={inputId}
          type="text"
          autoComplete="off"
          role="combobox"
          aria-expanded={open && suggestions.length > 0}
          aria-controls={listId}
          aria-invalid={!!error}
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            onChange({ label: e.target.value })
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
        />
        {picked && <span className="loc-ok" title="Location found">✓</span>}
        {loading && <span className="loc-spin" aria-label="Searching" />}
      </div>
      {open && suggestions.length > 0 && (
        <ul className="suggest" id={listId} role="listbox">
          {suggestions.map((r, i) => (
            <li
              key={`${r.lat},${r.lng},${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : ''}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(r)
              }}
              onMouseEnter={() => setActive(i)}
            >
              <strong>{r.short}</strong>
              <span>{r.label}</span>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
