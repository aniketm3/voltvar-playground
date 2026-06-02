import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ReferenceArea,
  LineChart, Line, Legend, ResponsiveContainer, Cell,
} from 'recharts'

const BUSES = ['632','633','634','645','646','671','684','611','652','680','692','675']

function barColor(v) {
  if (!v) return '#30363d'
  if (v < 0.95 || v > 1.05) return '#f85149'
  if (v < 0.97 || v > 1.03) return '#d29922'
  return '#3fb950'
}

function formatTime(step) {
  const m = step * 15
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

const CHART_STYLE = {
  fontSize: 10,
  background: 'transparent',
}

const AXIS_STYLE = { fill: '#8b949e', fontSize: 10 }
const TOOLTIP_STYLE = {
  background: '#161b22',
  border: '1px solid #30363d',
  borderRadius: 4,
  fontSize: 11,
  color: '#e6edf3',
}

// ── Single-step bar chart ─────────────────────────────────────────────────────

function SingleStepChart({ voltages }) {
  const data = BUSES.map(bus => ({ bus, v: voltages[bus] ?? null }))

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 10, left: -20, bottom: 0 }} style={CHART_STYLE}>
        <ReferenceArea y1={0.95} y2={1.05} fill="#3fb950" fillOpacity={0.07} />
        <XAxis dataKey="bus" tick={AXIS_STYLE} />
        <YAxis domain={[0.9, 1.1]} tick={AXIS_STYLE} tickCount={5} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={v => [v ? v.toFixed(4) + ' pu' : '—', 'Voltage']}
        />
        <ReferenceLine y={0.95} stroke="#f85149" strokeDasharray="3 3" strokeWidth={1} />
        <ReferenceLine y={1.05} stroke="#f85149" strokeDasharray="3 3" strokeWidth={1} />
        <Bar dataKey="v" radius={[2, 2, 0, 0]}>
          {data.map(({ bus, v }) => (
            <Cell key={bus} fill={barColor(v)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── Full-episode line chart ───────────────────────────────────────────────────

function EpisodeChart({ episode, currentStep }) {
  const data = episode.map(step => ({
    t:      step.timestep,
    time:   formatTime(step.timestep),
    v_min:  Math.min(...Object.values(step.voltages)),
    v_max:  Math.max(...Object.values(step.voltages)),
    viols:  step.n_violations,
  }))

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 10, left: -20, bottom: 0 }} style={CHART_STYLE}>
        <ReferenceArea y1={0.95} y2={1.05} fill="#3fb950" fillOpacity={0.07} />
        <XAxis
          dataKey="time"
          tick={AXIS_STYLE}
          interval={11}
        />
        <YAxis domain={[0.9, 1.1]} tick={AXIS_STYLE} tickCount={5} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(v, name) => [v.toFixed(4) + ' pu', name]}
          labelFormatter={label => `Time: ${label}`}
        />
        <ReferenceLine y={0.95} stroke="#f85149" strokeDasharray="3 3" strokeWidth={1} />
        <ReferenceLine y={1.05} stroke="#f85149" strokeDasharray="3 3" strokeWidth={1} />
        <ReferenceLine
          x={formatTime(currentStep)}
          stroke="#58a6ff"
          strokeDasharray="4 2"
          strokeWidth={1}
        />
        <Line
          type="monotone" dataKey="v_min" name="v_min"
          stroke="#3fb950" dot={false} strokeWidth={1.5}
        />
        <Line
          type="monotone" dataKey="v_max" name="v_max"
          stroke="#f59e0b" dot={false} strokeWidth={1.5}
        />
        <Legend wrapperStyle={{ fontSize: 10, color: '#8b949e' }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ── Export ────────────────────────────────────────────────────────────────────

export default function VoltageChart({ voltages, episode, currentStep }) {
  if (episode) {
    return <EpisodeChart episode={episode} currentStep={currentStep} />
  }
  return <SingleStepChart voltages={voltages} />
}
