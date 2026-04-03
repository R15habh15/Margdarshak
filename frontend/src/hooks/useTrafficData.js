/**
 * useTrafficData.js
 * Central data hook — manages simulation state, WebSocket stream,
 * and periodic metric polling for the entire dashboard.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { simulationApi, metricsApi, createSimulationSocket } from '../services/api'

const POLL_INTERVAL_MS = 2000  // poll status every 2s when not streaming

export function useTrafficData() {
  // ── Simulation status ──
  const [simStatus, setSimStatus]       = useState({ running: false, step: 0, mode: null })
  const [isLoading, setIsLoading]       = useState(false)
  const [error, setError]               = useState(null)

  // ── Live stream state (from WebSocket) ──
  const [liveState, setLiveState]       = useState(null)
  const [streamActive, setStreamActive] = useState(false)

  // ── Metrics ──
  const [currentMetrics, setCurrentMetrics] = useState(null)
  const [metricsHistory, setMetricsHistory] = useState([])
  const [comparison, setComparison]         = useState(null)

  // ── Traffic light states (for map) ──
  const [tlStates, setTlStates]         = useState({})

  const wsRef       = useRef(null)
  const pollRef     = useRef(null)

  // ── Helpers ──
  const clearError = () => setError(null)

  // ── Poll simulation status ──
  const pollStatus = useCallback(async () => {
    try {
      const status = await simulationApi.getStatus()
      setSimStatus(status)
    } catch (e) {
      // silently ignore poll errors
    }
  }, [])

  // ── Poll metrics when running ──
  const pollMetrics = useCallback(async () => {
    try {
      const [current, history] = await Promise.all([
        metricsApi.getCurrent(),
        metricsApi.getHistory(),
      ])
      setCurrentMetrics(current)
      setMetricsHistory(history.history || [])
    } catch (e) {
      // silently ignore
    }
  }, [])

  // ── Start WebSocket stream ──
  const startStream = useCallback(() => {
    if (wsRef.current) return

    wsRef.current = createSimulationSocket(
      (msg) => {
        if (msg.error) { setError(msg.error); return }
        setLiveState(msg)
        setStreamActive(true)

        // Extract TL states for map rendering
        if (msg.traffic_lights) {
          setTlStates(msg.traffic_lights)
        }

        // Update sim status from stream
        setSimStatus(prev => ({
          ...prev,
          running:  true,
          step:     msg.step,
          sim_time: msg.sim_time,
          mode:     msg.mode,
        }))
      },
      (e) => { setError('WebSocket error. Is the simulation running?'); setStreamActive(false) },
      (e) => { setStreamActive(false); wsRef.current = null; pollStatus() },
    )
  }, [pollStatus])

  // ── Stop WebSocket stream ──
  const stopStream = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setStreamActive(false)
  }, [])

  // ── Simulation controls ──
  const startSimulation = useCallback(async (configPath, mode = 'static') => {
    setIsLoading(true)
    setError(null)
    try {
      await simulationApi.start(configPath, mode)
      await pollStatus()
      startStream()
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [pollStatus, startStream])

  const stopSimulation = useCallback(async () => {
    setIsLoading(true)
    try {
      stopStream()
      await simulationApi.stop()
      await pollStatus()
      await pollMetrics()
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [stopStream, pollStatus, pollMetrics])

  const resetSimulation = useCallback(async () => {
    setIsLoading(true)
    try {
      stopStream()
      await simulationApi.reset()
      setLiveState(null)
      setTlStates({})
      await pollStatus()
      startStream()
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [stopStream, pollStatus, startStream])

  const switchMode = useCallback(async (mode) => {
    try {
      await simulationApi.setMode(mode)
      await pollStatus()
    } catch (e) {
      setError(e.message)
    }
  }, [pollStatus])

  const saveComparison = useCallback(async () => {
    try {
      await metricsApi.saveComparison()
      const comp = await metricsApi.getComparison()
      setComparison(comp)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  const fetchComparison = useCallback(async () => {
    try {
      const comp = await metricsApi.getComparison()
      setComparison(comp)
    } catch (e) {}
  }, [])

  const simRunningRef = useRef(false)
  useEffect(() => { simRunningRef.current = simStatus.running }, [simStatus.running])

  // ── Periodic polling ──
  useEffect(() => {
    pollStatus()
    pollRef.current = setInterval(() => {
      pollStatus()
      if (simRunningRef.current) pollMetrics()
    }, POLL_INTERVAL_MS)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      stopStream()
    }
  }, [pollStatus, pollMetrics, stopStream])

  // ── Poll metrics when sim is running ──
  useEffect(() => {
    if (simStatus.running) pollMetrics()
  }, [simStatus.running, pollMetrics])

  return {
    // State
    simStatus,
    liveState,
    streamActive,
    currentMetrics,
    metricsHistory,
    comparison,
    tlStates,
    isLoading,
    error,

    // Actions
    startSimulation,
    stopSimulation,
    resetSimulation,
    switchMode,
    saveComparison,
    fetchComparison,
    clearError,
    startStream,
    stopStream,
  }
}
