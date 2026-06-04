const PV_INVERTERS = [
  { name: 'PV675', bus: '675', kva: 500 },
  { name: 'PV680', bus: '680', kva: 400 },
  { name: 'PV611', bus: '611', kva: 150 },
  { name: 'PV652', bus: '652', kva: 150 },
]

// Sinusoidal solar profile matching the backend's profiles.py
function buildSolarCurve(solarScale, cloudCover) {
  return Array.from({ length: 96 }, (_, t) => ({
    t,
    v: Math.max(0, Math.sin(Math.PI * t / 96)) * solarScale * (1 - cloudCover),
  }))
}

function SolarSparkline({ solarScale, cloudCover, currentStep }) {
  const W = 200
  const H = 36
  const data = buildSolarCurve(solarScale, cloudCover)

  const pts = data.map(({ t, v }) => [
    (t / 95) * W,
    H - Math.min(v, 1.5) / 1.5 * (H - 2) - 1,
  ])

  const linePath = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L${W},${H} L0,${H} Z`

  const curX = ((currentStep / 95) * W).toFixed(1)

  return (
    <div className="sparkline-wrap">
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {/* Safe-zone band (≈0.95–1.05 pu effect) subtle fill */}
        <path d={areaPath} fill="rgba(217, 119, 6, 0.12)" />
        <path d={linePath} fill="none" stroke="#d97706" strokeWidth="1.5" />
        {/* Current timestep marker */}
        <line x1={curX} y1={0} x2={curX} y2={H} stroke="#2563eb" strokeWidth="1.5" strokeDasharray="3 2" />
      </svg>
    </div>
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
  timestep,
  loadScale, onLoadScale,
  solarScales, onSolarScale,
  cloudCovers, onCloudCover,
  selectedPV,
}) {
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
        {PV_INVERTERS.map(({ name, bus, kva }, idx) => {
          const isActive = selectedPV === name
          return (
            <div key={name} className="inverter-block">
              <div className={`inverter-name ${isActive ? 'active' : ''}`}>
                <span className="pv-dot" />
                {name}
                <span style={{ color: '#78716c', fontWeight: 400, marginLeft: 4 }}>
                  bus {bus} · {kva} kVA
                </span>
              </div>
              <Slider
                label="Solar"
                min={0} max={1.5} step={0.05}
                value={solarScales[idx]}
                onChange={v => onSolarScale(idx, v)}
                format={v => v.toFixed(2)}
              />
              <Slider
                label="Cloud"
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
