import { useEffect, useRef } from 'react'

/**
 * MapLayers — renders actual traffic signal icons on the Mapbox map.
 *
 * Each junction gets a DOM marker that looks like a real traffic light:
 *   ● Red light   (top)
 *   ● Yellow light (middle)
 *   ● Green light  (bottom)
 *
 * The currently active light glows brightly; the others are dim.
 * Phase mapping:
 *   phase 0 → GREEN  (main go phase)
 *   phase 1 → YELLOW (transition)
 *   phase 2+ → RED   (stop)
 *
 * Clicking a marker shows a popup with junction stats.
 */
export default function MapLayers({ map, tlStates }) {
  const markersRef = useRef({})   // tl_id → { marker, el }
  const popupRef   = useRef(null)

  // ── Inject global CSS for animation once ──────────────────────
  useEffect(() => {
    if (document.getElementById('tl-signal-styles')) return
    const style = document.createElement('style')
    style.id = 'tl-signal-styles'
    style.textContent = `
      .tl-signal-post {
        display: flex;
        flex-direction: column;
        align-items: center;
        cursor: pointer;
        user-select: none;
      }
      .tl-signal-box {
        background: #111827;
        border: 1.5px solid rgba(255,255,255,0.18);
        border-radius: 5px;
        padding: 3px 3px;
        display: flex;
        flex-direction: column;
        gap: 2.5px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.7);
      }
      .tl-light {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        transition: background 0.3s, box-shadow 0.3s;
      }
      .tl-light.dim-red    { background: #3d0a0a; box-shadow: none; }
      .tl-light.dim-yellow { background: #3d2e00; box-shadow: none; }
      .tl-light.dim-green  { background: #0a2d0a; box-shadow: none; }
      .tl-light.on-red     { background: #ff1744; box-shadow: 0 0 8px #ff1744, 0 0 16px rgba(255,23,68,0.5); }
      .tl-light.on-yellow  { background: #ffea00; box-shadow: 0 0 8px #ffea00, 0 0 16px rgba(255,234,0,0.5); }
      .tl-light.on-green   { background: #00e676; box-shadow: 0 0 8px #00e676, 0 0 16px rgba(0,230,118,0.5); }
      .tl-signal-stem {
        width: 2px;
        height: 6px;
        background: rgba(255,255,255,0.2);
        border-radius: 1px;
      }
      .tl-queue-badge {
        font-family: monospace;
        font-size: 8px;
        font-weight: bold;
        color: #fff;
        background: rgba(0,0,0,0.75);
        border-radius: 3px;
        padding: 1px 3px;
        margin-top: 1px;
        min-width: 14px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.15);
      }
    `
    document.head.appendChild(style)
  }, [])

  // ── Determine active light from SUMO phase ────────────────────
  function phaseToLight(phase) {
    if (phase === 0) return 'green'
    if (phase === 1) return 'yellow'
    return 'red'
  }

  // ── Build or update a signal marker DOM element ───────────────
  function applySignalState(el, phase, queue) {
    const active = phaseToLight(phase)
    el.querySelector('.tl-light-red').className    = `tl-light ${active === 'red'    ? 'on-red'    : 'dim-red'}`
    el.querySelector('.tl-light-yellow').className = `tl-light ${active === 'yellow' ? 'on-yellow' : 'dim-yellow'}`
    el.querySelector('.tl-light-green').className  = `tl-light ${active === 'green'  ? 'on-green'  : 'dim-green'}`
    const badge = el.querySelector('.tl-queue-badge')
    if (badge) badge.textContent = queue > 0 ? queue : ''
  }

  function createSignalElement(phase, queue) {
    const wrapper = document.createElement('div')
    wrapper.className = 'tl-signal-post'

    const box = document.createElement('div')
    box.className = 'tl-signal-box'

    const red    = document.createElement('div'); red.className    = 'tl-light dim-red';    red.classList.add('tl-light-red')
    const yellow = document.createElement('div'); yellow.className = 'tl-light dim-yellow'; yellow.classList.add('tl-light-yellow')
    const green  = document.createElement('div'); green.className  = 'tl-light dim-green';  green.classList.add('tl-light-green')

    box.appendChild(red)
    box.appendChild(yellow)
    box.appendChild(green)

    const stem  = document.createElement('div'); stem.className  = 'tl-signal-stem'
    const badge = document.createElement('div'); badge.className = 'tl-queue-badge'

    wrapper.appendChild(box)
    wrapper.appendChild(stem)
    wrapper.appendChild(badge)

    applySignalState(wrapper, phase, queue)
    return wrapper
  }

  // ── Update markers whenever tlStates changes ──────────────────
  useEffect(() => {
    if (!map || !tlStates) return

    import('mapbox-gl').then(({ default: mapboxgl }) => {
      const activeIds = new Set(Object.keys(tlStates))

      // Remove stale markers
      Object.keys(markersRef.current).forEach(id => {
        if (!activeIds.has(id)) {
          markersRef.current[id].remove()
          delete markersRef.current[id]
        }
      })

      // Add / update markers
      Object.entries(tlStates).forEach(([id, data]) => {
        if (!data.lng || !data.lat) return

        const phase = data.phase ?? 0
        const queue = data.total_queue ?? 0

        if (markersRef.current[id]) {
          // Update existing marker's DOM
          const el = markersRef.current[id].getElement()
          applySignalState(el, phase, queue)
          markersRef.current[id].setLngLat([data.lng, data.lat])
        } else {
          // Create new marker
          const el = createSignalElement(phase, queue)

          // Click popup
          el.addEventListener('click', () => {
            if (popupRef.current) popupRef.current.remove()
            popupRef.current = new mapboxgl.Popup({ closeButton: true, maxWidth: '200px', offset: 18 })
              .setLngLat([data.lng, data.lat])
              .setHTML(`
                <div style="font-family:monospace;font-size:11px;color:#e2e8f0;background:#0f172a;padding:10px 12px;border-radius:8px;line-height:1.6">
                  <div style="color:#00e5ff;font-weight:bold;margin-bottom:6px">🚦 ${id}</div>
                  <div>Phase: <b style="color:#fff">${data.phase}</b></div>
                  <div>Vehicles: <b style="color:#fff">${data.total_vehicles ?? 0}</b></div>
                  <div>Queue: <b style="color:${queue > 5 ? '#ff4444' : '#44ff88'}">${queue}</b></div>
                  <div>Wait: <b style="color:#fff">${Math.round(data.total_wait ?? 0)}s</b></div>
                </div>
              `)
              .addTo(map)
          })

          const marker = new mapboxgl.Marker({ element: el, anchor: 'bottom' })
            .setLngLat([data.lng, data.lat])
            .addTo(map)

          markersRef.current[id] = marker
        }
      })
    })
  }, [map, tlStates])

  // ── Cleanup on unmount ────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (popupRef.current) { popupRef.current.remove(); popupRef.current = null }
      Object.values(markersRef.current).forEach(m => m.remove())
      markersRef.current = {}
    }
  }, [])

  return null
}
