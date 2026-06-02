// PV inverter metadata — order matches solarScales/cloudCovers index in the backend.
const PV_INVERTERS = [
  { name: 'PV675', bus: '675', kva: 500 },
  { name: 'PV680', bus: '680', kva: 400 },
  { name: 'PV611', bus: '611', kva: 150 },
  { name: 'PV652', bus: '652', kva: 150 },
]

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
  loadScale, onLoadScale,
  solarScales, onSolarScale,
  cloudCovers, onCloudCover,
  selectedPV,
}) {
  return (
    <>
      {/* Global load scale */}
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

      {/* Per-inverter controls */}
      <div className="control-section">
        <div className="section-title">PV Inverters</div>
        {PV_INVERTERS.map(({ name, bus, kva }, idx) => {
          const isActive = selectedPV === name
          return (
            <div key={name} className="inverter-block">
              <div className={`inverter-name ${isActive ? 'active' : ''}`}>
                <span className="pv-dot" />
                {name}
                <span style={{ color: '#8b949e', fontWeight: 400, marginLeft: 4 }}>
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
            </div>
          )
        })}
      </div>
    </>
  )
}
