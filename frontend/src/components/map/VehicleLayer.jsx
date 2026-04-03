import { useEffect, useRef } from 'react'

/**
 * VehicleLayer — renders individual moving vehicles as nodes on the map.
 */
export default function VehicleLayer({ map, liveState }) {
  const isAdded = useRef(false)
  const markerRef = useRef(null) // test marker
  const SOURCE_ID = 'vehicles-source'
  const LAYER_ID  = 'vehicles-layer'

  useEffect(() => {
    if (!map) return

    const updateMap = () => {
      if (!map.getStyle()) return

      // 1. Initial Source/Layer Setup
      if (!isAdded.current || !map.getSource(SOURCE_ID)) {
        try {
          if (!map.getSource(SOURCE_ID)) {
            map.addSource(SOURCE_ID, { 
              type: 'geojson', 
              data: { type: 'FeatureCollection', features: [] } 
            })

            // Find a layer to insert BEFORE (so they are under labels but above roads)
            const layers = map.getStyle().layers
            let labelLayerId
            for (let i = 0; i < layers.length; i++) {
              if (layers[i].type === 'symbol' && layers[i].layout['text-field']) {
                labelLayerId = layers[i].id
                break
              }
            }

            map.addLayer({
              id:     LAYER_ID,
              type:   'symbol',
              source: SOURCE_ID,
              layout: {
                'text-field': '▲',
                'text-size': [
                  'interpolate', ['linear'], ['zoom'],
                  14, 12,
                  18, 28
                ],
                'text-rotate': ['get', 'angle'],
                'text-rotation-alignment': 'map',
                'text-pitch-alignment': 'map',
                'text-allow-overlap': true,
                'text-ignore-placement': true,
              },
              paint: {
                'text-color': [
                  'interpolate', ['linear'], ['get', 'speed'],
                  0,  '#ff3b3b',  // Red (stuck)
                  15, '#ffcc00',  // Yellow (slow moving)
                  40, '#00e5ff'   // Cyan (free flow)
                ],
                'text-halo-color': '#000000',
                'text-halo-width': 1,
              },
            }, labelLayerId)
          }
          isAdded.current = true
        } catch (e) {
          console.warn("[VehicleLayer] Setup failed", e)
          return
        }
      }

      // 2. Data Update
      if (liveState?.vehicles) {
        const features = liveState.vehicles.map(veh => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [veh.lng, veh.lat] },
          properties: { 
            id: veh.id, 
            speed: veh.speed ?? 0,
            angle: (veh.angle ?? 0)
          },
        }))

        try {
          const source = map.getSource(SOURCE_ID)
          if (source) {
            source.setData({ type: 'FeatureCollection', features })
          }

          // Test marker: put a real DOM marker on the first car
          if (features.length > 0) {
            import('mapbox-gl').then(({ default: mapboxgl }) => {
              if (!markerRef.current) {
                markerRef.current = new mapboxgl.Marker({ color: '#ff00ff' })
                  .setLngLat(features[0].geometry.coordinates)
                  .addTo(map)
              } else {
                markerRef.current.setLngLat(features[0].geometry.coordinates)
              }
            })
          }
        } catch (e) {
          console.warn("[VehicleLayer] Data sync failed", e)
        }
      }
    }

    if (map.isStyleLoaded()) updateMap()
    else map.on('styledata', updateMap)

    return () => {
      map.off('styledata', updateMap)
      if (markerRef.current) {
        markerRef.current.remove()
        markerRef.current = null
      }
      if (map && isAdded.current) {
        try {
          if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID)
          if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
          isAdded.current = false
        } catch (_) {}
      }
    }
  }, [map, liveState])

  return null
}
