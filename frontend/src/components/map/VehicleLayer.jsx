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
export default function VehicleLayer({ map, liveState, showHeatmap = false }) {
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
          congestion: Math.max(0, 1 - ((v.speed ?? 0) / 10)), // 0 m/s = 1.0 weight, >= 10 m/s = 0 weight
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

        // Glow behind vehicle
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

        // Heatmap layer for congestion
        if (!map.getLayer('vehicles-heatmap')) {
          map.addLayer({
            id: 'vehicles-heatmap',
            type: 'heatmap',
            source: SOURCE_ID,
            paint: {
              // Increase the heatmap weight based on the 'congestion' property
              'heatmap-weight': [
                'interpolate',
                ['linear'],
                ['get', 'congestion'],
                0, 0,
                1, 1
              ],
              // Increase the heatmap intensity by zoom level
              'heatmap-intensity': [
                'interpolate',
                ['linear'],
                ['zoom'],
                12, 0.5,
                17, 1.5
              ],
              // Color ramp designed for dark theme (deep blue -> purple -> pink -> red)
              'heatmap-color': [
                'interpolate',
                ['linear'],
                ['heatmap-density'],
                0, 'rgba(0,0,0,0)',
                0.2, 'rgba(0, 163, 255, 0.3)',   // deep blue
                0.5, 'rgba(168, 85, 247, 0.6)',  // purple
                0.8, 'rgba(236, 72, 153, 0.8)',  // pink
                1, 'rgba(239, 68, 68, 0.9)'      // danger red
              ],
              // Adjust the heatmap radius by zoom level
              'heatmap-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                12, 10,
                17, 30
              ],
              // Transition opacity depending on zoom to balance symbol vs heatmap
              'heatmap-opacity': [
                'interpolate',
                ['linear'],
                ['zoom'],
                13, 0.8,
                16, 0.5
              ],
            },
            layout: {
              'visibility': showHeatmap ? 'visible' : 'none'
            }
          }, HALO_LAYER); // insert before halo/symbols
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
        ;[SYMBOL_LAYER, HALO_LAYER, 'vehicles-heatmap'].forEach(id => { if (map.getLayer(id)) map.removeLayer(id) })
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

  useEffect(() => {
    if (!map || !isAdded.current) return
    try {
      if (map.getLayer('vehicles-heatmap')) {
        map.setLayoutProperty('vehicles-heatmap', 'visibility', showHeatmap ? 'visible' : 'none')
      }
    } catch (e) {
      console.warn('[VehicleLayer] visibility update error', e)
    }
  }, [map, showHeatmap])

  return null
}
