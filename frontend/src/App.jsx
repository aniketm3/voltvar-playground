import { useState, useEffect, useRef, useCallback } from 'react'
import GridGraph from './components/GridGraph.jsx'
import VoltageChart from './components/VoltageChart.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import InfoModal from './components/InfoModal.jsx'
import { simulateStep, simulateEpisode } from './api.js'

const POLICIES = [
  { value: 'lag_sac_both',      label: 'Lag-SAC + domain-rand ★' },
  { value: 'lag_sac_curriculum', label: 'Lag-SAC + curriculum' },
  { value: 'sac_both',          label: 'SAC + domain-rand' },
  { value: 'sac_none',          label: 'SAC (no DR)' },
  { value: 'droop',             label: 'Droop (IEEE 1547)' },
  { value: 'zero',              label: 'Zero VAR' },
]

function formatTime(step) {
  const mins = step * 15
  const hh = String(Math.floor(mins / 60)).padStart(2, '0')
  const mm = String(mins % 60).padStart(2, '0')
  return `${hh}:${mm}`
}

export default function App() {
  // Default to the interesting demo scenario: noon, full sun, light load.
  // At these settings lag_sac_both shows 1 violation vs droop's 0 (but 3x better losses).
  const [policy,       setPolicy]       = useState('lag_sac_both')
  const [timestep,     setTimestep]     = useState(48)
  const [solarScales,  setSolarScales]  = useState([1.5, 1.5, 1.5, 1.5])
  const [cloudCovers,  setCloudCovers]  = useState([0, 0, 0, 0])
  const [loadScale,    setLoadScale]    = useState(0.5)
  const [selectedPV,   setSelectedPV]   = useState(null)

  const [result,       setResult]       = useState(null)
  const [episode,      setEpisode]      = useState(null)
  const [loading,      setLoading]      = useState(false)
  const [epLoading,    setEpLoading]    = useState(false)
  const [error,        setError]        = useState(null)
  const [showInfo,     setShowInfo]     = useState(false)

  const debounceRef = useRef(null)

  const runStep = useCallback(async (params) => {
    setLoading(true)
    setError(null)
    try {
      const res = await simulateStep(params)
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Debounced re-simulation on any control change.
  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      runStep({ policy, timestep, solarScales, cloudCovers, loadScale })
    }, 200)
    return () => clearTimeout(debounceRef.current)
  }, [policy, timestep, solarScales, cloudCovers, loadScale, runStep])

  async function handleRunEpisode() {
    setEpLoading(true)
    setError(null)
    try {
      const res = await simulateEpisode({ policy, solarScales, cloudCovers, loadScale })
      setEpisode(res.episode)
    } catch (e) {
      setError(e.message)
    } finally {
      setEpLoading(false)
    }
  }

  function handleSolarScale(idx, val) {
    setSolarScales(prev => prev.map((v, i) => i === idx ? val : v))
    setEpisode(null)
  }
  function handleCloudCover(idx, val) {
    setCloudCovers(prev => prev.map((v, i) => i === idx ? val : v))
    setEpisode(null)
  }
  function handlePolicyChange(val) { setPolicy(val); setEpisode(null) }
  function handleLoadScale(val)    { setLoadScale(val); setEpisode(null) }

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <h1>VoltVAR Explorer</h1>

        <div className="header-control">
          <label>Policy</label>
          <select value={policy} onChange={e => handlePolicyChange(e.target.value)}>
            {POLICIES.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="header-control">
          <label>Time</label>
          <input
            type="range" min={0} max={95} value={timestep}
            onChange={e => { setTimestep(Number(e.target.value)); setEpisode(null) }}
            style={{ width: 160 }}
          />
          <span className="time-display">{formatTime(timestep)}</span>
        </div>

        {error  && <span className="error-banner">{error}</span>}
        {loading && <span className="loading-dot" />}
        <button className="info-btn" onClick={() => setShowInfo(true)} title="About this app">ⓘ</button>
      </header>

      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}

      {/* ── Body ── */}
      <div className="app-body">
        {/* Left: graph + chart */}
        <div className="left-col">
          <div className="graph-area">
            <GridGraph
              voltages={result?.voltages ?? {}}
              violationBuses={result?.violation_buses ?? []}
              selectedPV={selectedPV}
              onSelectPV={setSelectedPV}
            />
          </div>

          <div className="chart-area">
            <div className="chart-header">
              <span className="chart-title">
                {episode ? 'Full Episode — min/max voltage' : 'Bus Voltages'}
              </span>
              <button
                className="btn btn-primary"
                onClick={handleRunEpisode}
                disabled={epLoading}
              >
                {epLoading ? 'Running…' : '▶ Run Full Episode'}
              </button>
            </div>
            <VoltageChart
              voltages={result?.voltages ?? {}}
              episode={episode}
              currentStep={timestep}
            />
          </div>
        </div>

        {/* Right: controls + stats */}
        <div className="right-col">
          <ControlPanel
            timestep={timestep}
            loadScale={loadScale}
            onLoadScale={handleLoadScale}
            solarScales={solarScales}
            onSolarScale={handleSolarScale}
            cloudCovers={cloudCovers}
            onCloudCover={handleCloudCover}
            selectedPV={selectedPV}
          />
          <StatsPanel result={result} />
        </div>
      </div>
    </div>
  )
}
