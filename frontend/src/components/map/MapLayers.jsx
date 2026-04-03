import { useEffect, useRef } from 'react'

/**
 * MapLayers — renders traffic light junction markers on the Mapbox map.
 * Each junction is colored by congestion level.
 */
export default function MapLayers({ map, tlStates }) {
  const isAdded = useRef(false)
  const SOURCE_ID = 'tl-junctions'
  const LAYER_ID  = 'tl-circles'

  // 1. Initialization logic
  useEffect(() => {
    if (!map) return

    const setup = () => {
      if (!map.getStyle() || isAdded.current) return
      
      try {
        if (!map.getSource(SOURCE_ID)) {
          map.addSource(SOURCE_ID, { 
            type: 'geojson', 
            data: { type: 'FeatureCollection', features: [] } 
          })
          map.addLayer({
            id:     LAYER_ID,
            type:   'circle',
            source: SOURCE_ID,
            paint: {
              'circle-radius': [
                'interpolate', ['linear'], ['get', 'vehicles'],
                0,  12,
                20, 35
              ],
              'circle-color': [
                'interpolate', ['linear'], ['get', 'vehicles'],
                0,  '#00ff00',  // Green (clear)
                10, '#ffff00',  // Yellow (busy)
                25, '#ff0000'   // Heat!
              ],
              'circle-opacity': 0.6,
              'circle-blur': 0.7, // Heatmap look
            },
          })
        }
        isAdded.current = true
      } catch (e) {
        console.warn("Could not setup MapLayers", e)
      }
    }

    if (map.isStyleLoaded()) setup()
    else map.once('style.load', setup)

    return () => {
      try {
        if (map.getLayer(LAYER_ID))  map.removeLayer(LAYER_ID)
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
        isAdded.current = false
      } catch (_) {}
    }
  }, [map])

  // 2. Data Update logic
  useEffect(() => {
    if (!map || !tlStates || !isAdded.current) return

    const features = Object.entries(tlStates).map(([id, data]) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [data.lng, data.lat] },
      properties: {
        id,
        phase:    data.phase ?? 0,
        vehicles: data.total_vehicles ?? 0,
        queue:    data.total_queue    ?? 0,
        wait:     data.total_wait     ?? 0,
      },
    }))

    try {
      const source = map.getSource(SOURCE_ID)
      if (source) {
        source.setData({ type: 'FeatureCollection', features })
      }
    } catch (e) {
      console.warn("MapLayers data update failed", e)
    }
  }, [map, tlStates])

  return null
}
