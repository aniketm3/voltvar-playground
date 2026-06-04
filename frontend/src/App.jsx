import { useState, useEffect, useRef, useCallback } from 'react'
import FeedersScreen from './screens/FeedersScreen.jsx'
import GridGraph from './components/GridGraph.jsx'
import VoltageChart from './components/VoltageChart.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import InfoModal from './components/InfoModal.jsx'
import { getGrids, simulateStep, simulateEpisode } from './api.js'

const POLICY_LABELS = {
  lag_sac_both:       'Lag-SAC + DR ★',
  lag_sac_curriculum: 'Lag-SAC + Curriculum',
  sac_both:           'SAC + DR',
  sac_none:           'SAC (no DR)',
  droop:              'Droop (IEEE 1547)',
  zero:               'Zero VAR',
}

function formatTime(step) {
  const mins = step * 15
  return `${String(Math.floor(mins / 60)).padStart(2,'0')}:${String(mins % 60).padStart(2,'0')}`
}

// ── Grid Explorer (main simulation screen) ───────────────────────────────────

function GridScreen({ grid, onBack }) {
  const defaultPolicy = grid.available_models.find(m => m.startsWith('lag_sac'))
    ?? grid.available_models[0]

  const [policy,      setPolicy]      = useState(defaultPolicy)
  const [timestep,    setTimestep]    = useState(grid.default_timestep)
  const [solarScales, setSolarScales] = useState(grid.default_solar_scales)
  const [cloudCovers, setCloudCovers] = useState(grid.default_cloud_covers)
  const [loadScale,   setLoadScale]   = useState(grid.default_load_scale)
  const [selectedPV,  setSelectedPV]  = useState(null)

  const [result,      setResult]      = useState(null)
  const [episode,     setEpisode]     = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [epLoading,   setEpLoading]   = useState(false)
  const [error,       setError]       = useState(null)
  const [showInfo,    setShowInfo]    = useState(false)

  const debounceRef = useRef(null)

  const runStep = useCallback(async (params) => {
    setLoading(true)
    setError(null)
    try {
      setResult(await simulateStep(params))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      runStep({ gridId: grid.id, policy, timestep, solarScales, cloudCovers, loadScale })
    }, 200)
    return () => clearTimeout(debounceRef.current)
  }, [grid.id, policy, timestep, solarScales, cloudCovers, loadScale, runStep])

  async function handleRunEpisode() {
    setEpLoading(true)
    setError(null)
    try {
      const res = await simulateEpisode({ gridId: grid.id, policy, solarScales, cloudCovers, loadScale })
      setEpisode(res.episode)
    } catch (e) {
      setError(e.message)
    } finally {
      setEpLoading(false)
    }
  }

  function handleSolarScale(idx, val) { setSolarScales(p => p.map((v,i) => i===idx ? val : v)); setEpisode(null) }
  function handleCloudCover(idx, val) { setCloudCovers(p => p.map((v,i) => i===idx ? val : v)); setEpisode(null) }
  function handlePolicy(val)          { setPolicy(val);    setEpisode(null) }
  function handleLoadScale(val)       { setLoadScale(val); setEpisode(null) }

  return (
    <div className="app">
      <header className="app-header">
        <button className="back-btn" onClick={onBack}>← Feeders</button>
        <span className="header-divider" />
        <h1>{grid.name}</h1>

        <div className="header-control">
          <label>Policy</label>
          <select value={policy} onChange={e => handlePolicy(e.target.value)}>
            {grid.available_models.map(m => (
              <option key={m} value={m}>{POLICY_LABELS[m] ?? m}</option>
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
        <button className="info-btn" onClick={() => setShowInfo(true)}>ⓘ</button>
      </header>

      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}

      <div className="app-body">
        <div className="left-col">
          <div className="graph-area">
            <GridGraph
              grid={grid}
              voltages={result?.voltages ?? {}}
              selectedPV={selectedPV}
              onSelectPV={setSelectedPV}
            />
          </div>

          <div className="chart-area">
            <div className="chart-header">
              <span className="chart-title">
                {episode ? 'Full Episode — min/max voltage' : 'Bus Voltages'}
              </span>
              <button className="btn btn-primary" onClick={handleRunEpisode} disabled={epLoading}>
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

        <div className="right-col">
          <ControlPanel
            grid={grid}
            timestep={timestep}
            loadScale={loadScale}    onLoadScale={handleLoadScale}
            solarScales={solarScales} onSolarScale={handleSolarScale}
            cloudCovers={cloudCovers} onCloudCover={handleCloudCover}
            selectedPV={selectedPV}
          />
          <StatsPanel result={result} />
        </div>
      </div>
    </div>
  )
}

// ── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [grids,        setGrids]        = useState(null)
  const [selectedGrid, setSelectedGrid] = useState(null)
  const [loadError,    setLoadError]    = useState(null)

  useEffect(() => {
    getGrids()
      .then(setGrids)
      .catch(e => setLoadError(e.message))
  }, [])

  if (loadError) {
    return (
      <div style={{ padding: 40, color: 'var(--red)', fontFamily: 'monospace' }}>
        Failed to connect to backend: {loadError}
      </div>
    )
  }

  if (selectedGrid) {
    return <GridScreen grid={selectedGrid} onBack={() => setSelectedGrid(null)} />
  }

  return <FeedersScreen grids={grids} onSelect={setSelectedGrid} />
}
