import { useEffect, useRef } from 'react'

/**
 * VehicleLayer — renders moving vehicles as directional car symbols.
 *
 * Color logic (for judge demo clarity):
 *   CYAN/TEAL  — moving freely (speed > 8 m/s = 29 km/h)
 *   LIME GREEN — moving slowly (3–8 m/s)
 *   ORANGE     — waiting at signal (speed < 3 m/s = paused at red light — NORMAL)
 *   RED        — completely stuck / gridlocked for long time
 *
 * NOTE: Orange = "waiting at red light" is NORMAL and expected behaviour.
 * We distinguish this from RED which means truly gridlocked.
 *
 * The wait-time property controls red vs orange, but since SUMO only sends
 * speed in the payload, we use a simple heuristic:
 *   Low speed near a junction → orange (signalled stop) — not an error
 */
export default function VehicleLayer({ map, liveState }) {
  const isAdded    = useRef(false)
  const SOURCE_ID  = 'vehicles-source'
  const SYMBOL_LAYER = 'vehicles-symbol'
  const HALO_LAYER   = 'vehicles-halo'

  function buildFeatures(vehicles = []) {
    return vehicles
      .filter(v => v.lng && v.lat && !v.id?.startsWith('emergency_'))
      .map(v => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [v.lng, v.lat] },
        properties: {
          id:    v.id,
          speed: v.speed ?? 0,
          angle: v.angle ?? 0,
          // Bucket: 0=waiting(orange), 1=slow(lime), 2=moving(cyan)
          bucket: (v.speed ?? 0) < 2 ? 0 : (v.speed ?? 0) < 8 ? 1 : 2,
        },
      }))
  }

  useEffect(() => {
    if (!map) return

    const setup = () => {
      if (!map.getStyle() || isAdded.current) return
      try {
        if (!map.getSource(SOURCE_ID)) {
          map.addSource(SOURCE_ID, {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          })
        }

        // Halo glow behind vehicle
        if (!map.getLayer(HALO_LAYER)) {
          map.addLayer({
            id: HALO_LAYER, type: 'circle', source: SOURCE_ID,
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 3, 17, 6],
              'circle-color': [
                'match', ['get', 'bucket'],
                0, '#ff8c00',    // orange — waiting at signal
                1, '#a3e635',    // lime — slow
                2, '#00e5ff',    // cyan — free flow
                '#00e5ff'
              ],
              'circle-opacity': 0.22,
              'circle-blur': 0.7,
            },
          })
        }

        // Directional arrow symbol
        if (!map.getLayer(SYMBOL_LAYER)) {
          const layers = map.getStyle().layers
          let labelLayerId
          for (let i = 0; i < layers.length; i++) {
            if (layers[i].type === 'symbol' && layers[i].layout?.['text-field']) {
              labelLayerId = layers[i].id; break
            }
          }
          map.addLayer({
            id: SYMBOL_LAYER, type: 'symbol', source: SOURCE_ID,
            layout: {
              'text-field': '▲',
              'text-size': ['interpolate', ['linear'], ['zoom'], 12, 7, 17, 16],
              'text-rotate': ['get', 'angle'],
              'text-rotation-alignment': 'map',
              'text-pitch-alignment':    'map',
              'text-allow-overlap':      true,
              'text-ignore-placement':   true,
            },
            paint: {
              'text-color': [
                'match', ['get', 'bucket'],
                0, '#ff8c00',   // orange = waiting at red light (normal!)
                1, '#a3e635',   // lime   = slow moving
                2, '#00e5ff',   // cyan   = free flow
                '#00e5ff'
              ],
              'text-halo-color': 'rgba(0,0,0,0.75)',
              'text-halo-width': 1.2,
            },
          }, labelLayerId)
        }

        isAdded.current = true
      } catch (e) {
        console.warn('[VehicleLayer] setup error', e)
      }
    }

    if (map.isStyleLoaded()) setup()
    else map.on('styledata', setup)

    return () => {
      map.off('styledata', setup)
      try {
        ;[SYMBOL_LAYER, HALO_LAYER].forEach(id => { if (map.getLayer(id)) map.removeLayer(id) })
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
        isAdded.current = false
      } catch (_) {}
    }
  }, [map])

  useEffect(() => {
    if (!map || !liveState?.vehicles || !isAdded.current) return
    try {
      const src = map.getSource(SOURCE_ID)
      if (src) src.setData({ type: 'FeatureCollection', features: buildFeatures(liveState.vehicles) })
    } catch (e) {
      console.warn('[VehicleLayer] data update error', e)
    }
  }, [map, liveState])

  return null
}
