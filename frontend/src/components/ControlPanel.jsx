// Default used before grid config loads
const DEFAULT_PV_INVERTERS = []

function SolarSparkline({ solarScale, cloudCover, currentStep }) {
  const W = 200, H = 44

  const scaleY = v => H - Math.min(v, 1.5) / 1.5 * (H - 4) - 2

  const times = Array.from({ length: 96 }, (_, t) => {
    const raw = Math.max(0, Math.sin(Math.PI * t / 96))
    return {
      x: (t / 95) * W,
      pot: raw * solarScale,
      act: raw * solarScale * (1 - cloudCover),
    }
  })

  const potLine = times.map(({ x, pot }, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${scaleY(pot).toFixed(1)}`).join(' ')
  const actLine = times.map(({ x, act }, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${scaleY(act).toFixed(1)}`).join(' ')
  const actArea = `${actLine} L${W},${H} L0,${H} Z`
  const lossArea = `${potLine} L${W},${H} L0,${H} Z`

  const curX = ((currentStep / 95) * W).toFixed(1)

  return (
    <>
      <div className="sparkline-header">
        <span className="sparkline-label">24h profile</span>
        <span className="sparkline-legend">
          <span style={{ color: '#d29922', opacity: 0.5 }}>- -</span> clear sky
          <span style={{ margin: '0 2px', opacity: 0.4 }}>·</span>
          <span style={{ color: '#d29922' }}>—</span> w/ clouds
        </span>
      </div>
      <div className="sparkline-wrap">
        <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          {/* Cloud loss zone fills from potential down to bottom */}
          <path d={lossArea} fill="rgba(248, 81, 73, 0.07)" />
          {/* Actual output area */}
          <path d={actArea} fill="rgba(210, 153, 34, 0.18)" />
          {/* Clear-sky potential line */}
          <path d={potLine} fill="none" stroke="#d29922" strokeWidth="1" strokeDasharray="3 2" opacity="0.5" />
          {/* Actual output line */}
          <path d={actLine} fill="none" stroke="#d29922" strokeWidth="1.5" />
          {/* Current timestep marker */}
          <line x1={curX} y1={0} x2={curX} y2={H} stroke="#58a6ff" strokeWidth="1.5" strokeDasharray="3 2" />
        </svg>
      </div>
    </>
  )
}

function Slider({ label, min, max, step, value, onChange, format }) {
  return (
    <div className="slider-row">
      <span className="slider-label">{label}</span>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
      />
      <span className="slider-val">{format ? format(value) : value}</span>
    </div>
  )
}

export default function ControlPanel({
  grid,
  timestep,
  loadScale, onLoadScale,
  solarScales, onSolarScale,
  cloudCovers, onCloudCover,
  selectedPV,
}) {
  // Build inverter list from grid config
  const pvInverters = grid
    ? grid.pv_names.map((name, i) => ({
        name,
        bus: grid.pv_buses[name],
        kva: grid.pv_kva[i],
      }))
    : DEFAULT_PV_INVERTERS

  return (
    <>
      <div className="control-section">
        <div className="section-title">Grid Conditions</div>
        <Slider
          label="Load"
          min={0.5} max={1.5} step={0.05}
          value={loadScale}
          onChange={onLoadScale}
          format={v => `×${v.toFixed(2)}`}
        />
      </div>

      <div className="control-section">
        <div className="section-title">PV Inverters</div>
        <div className="section-hint">Each inverter has its own independent 24h solar profile</div>
        {pvInverters.map(({ name, bus, kva }, idx) => {
          const isActive = selectedPV === name
          return (
            <div key={name} className="inverter-block">
              <div className={`inverter-name ${isActive ? 'active' : ''}`}>
                <span className="pv-dot" />
                {name}
                <span style={{ color: 'var(--muted)', fontWeight: 400, marginLeft: 4 }}>
                  bus {bus} · {kva} kVA
                </span>
              </div>
              <Slider
                label="☀ Peak"
                min={0} max={1.5} step={0.05}
                value={solarScales[idx]}
                onChange={v => onSolarScale(idx, v)}
                format={v => v.toFixed(2)}
              />
              <Slider
                label="☁ Cover"
                min={0} max={1} step={0.05}
                value={cloudCovers[idx]}
                onChange={v => onCloudCover(idx, v)}
                format={v => `${Math.round(v * 100)}%`}
              />
              <SolarSparkline
                solarScale={solarScales[idx]}
                cloudCover={cloudCovers[idx]}
                currentStep={timestep}
              />
            </div>
          )
        })}
      </div>
    </>
  )
}
