import { useRef } from 'react'

const DEFAULT_PV_INVERTERS = []

function SolarProfileEditor({ solarScale, cloudProfile, onCloudProfile, onReset, onHourDrag, currentStep }) {
  const W = 200, H = 80
  const N = 24
  const BAR_W = W / N
  const svgRef = useRef(null)
  const dragging = useRef(false)

  const hours = Array.from({ length: N }, (_, h) => {
    const t = h * 4 + 2  // midpoint 15-min step for this hour
    const potential = Math.max(0, Math.sin(Math.PI * t / 96)) * solarScale
    const effective = potential * (1 - cloudProfile[h])
    return { potential, effective }
  })

  const toBarH = v => Math.round((Math.min(v, 1.5) / 1.5) * (H - 4))

  function applyDrag(e) {
    if (!dragging.current || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const h = Math.max(0, Math.min(N - 1, Math.floor((cx / rect.width) * N)))
    const { potential } = hours[h]
    if (potential <= 0.01) return
    const fraction = 1 - Math.max(0, Math.min(1, cy / rect.height))
    const newEffective = Math.min(fraction * 1.5, potential)
    onCloudProfile(h, Math.max(0, Math.min(1, 1 - newEffective / potential)))
    onHourDrag(h * 4 + 2)
  }

  const currentHour = Math.floor(currentStep / 4)

  return (
    <>
      <div className="sparkline-header">
        <span className="sparkline-label">24h solar profile</span>
        <span className="sparkline-legend">
          drag · ↑ clear  ↓ overcast
          <button className="profile-reset-btn" onClick={onReset} title="Reset to default">↺</button>
        </span>
      </div>
      <div className="sparkline-wrap">
        <svg
          ref={svgRef}
          width="100%" height="100%"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ cursor: 'ns-resize', display: 'block', userSelect: 'none' }}
          onMouseDown={e => { dragging.current = true; applyDrag(e) }}
          onMouseMove={applyDrag}
          onMouseUp={() => { dragging.current = false }}
          onMouseLeave={() => { dragging.current = false }}
        >
          {hours.map(({ potential, effective }, h) => {
            const isDay = potential > 0.01
            const isCurrent = h === currentHour
            const potH = toBarH(potential)
            const effH = toBarH(effective)
            const x = h * BAR_W + 0.5
            const bw = BAR_W - 1

            return (
              <g key={h}>
                {isDay ? (
                  <>
                    {/* Clear-sky potential — dim background */}
                    <rect
                      x={x} y={H - potH - 2} width={bw} height={potH}
                      fill={isCurrent ? 'rgba(210,153,34,0.22)' : 'rgba(210,153,34,0.1)'}
                    />
                    {/* Effective output after clouds */}
                    {effH > 0 && (
                      <rect
                        x={x} y={H - effH - 2} width={bw} height={effH}
                        fill={isCurrent ? 'rgba(210,153,34,0.95)' : 'rgba(210,153,34,0.6)'}
                      />
                    )}
                  </>
                ) : (
                  <rect x={x} y={H - 2} width={bw} height={2} fill="rgba(139,148,158,0.15)" />
                )}
              </g>
            )
          })}

          {/* Hour tick marks at 6h, 12h, 18h */}
          {[6, 12, 18].map(h => (
            <line key={h}
              x1={(h / N) * W} y1={H - 5} x2={(h / N) * W} y2={H}
              stroke="rgba(139,148,158,0.4)" strokeWidth="1"
            />
          ))}

          {/* Current timestep marker */}
          <line
            x1={currentHour * BAR_W + BAR_W / 2} y1={0}
            x2={currentHour * BAR_W + BAR_W / 2} y2={H}
            stroke="#58a6ff" strokeWidth="1" strokeDasharray="2 2" opacity="0.7"
          />
        </svg>
      </div>
      <div className="profile-time-labels">
        <span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>24h</span>
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
  cloudProfiles, onCloudProfile,
  onResetProfile,
  onTimestep,
  selectedPV,
}) {
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
        <div className="section-hint">Draw a custom 24h weather profile per inverter</div>
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
              <SolarProfileEditor
                solarScale={solarScales[idx]}
                cloudProfile={cloudProfiles[idx]}
                onCloudProfile={(h, v) => onCloudProfile(idx, h, v)}
                onReset={() => onResetProfile(idx)}
                onHourDrag={onTimestep}
                currentStep={timestep}
              />
            </div>
          )
        })}
      </div>
    </>
  )
}
