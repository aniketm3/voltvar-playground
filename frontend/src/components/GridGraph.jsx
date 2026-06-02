/**
 * SVG visualization of the IEEE 13-bus feeder.
 * Buses are colored by voltage safety; PV inverter buses are clickable.
 */

const W = 620
const H = 440

// Fixed bus coordinates for this SVG viewport.
const BUS_POS = {
  '650': { x: 52,  y: 220 },
  '632': { x: 180, y: 220 },
  '633': { x: 180, y: 115 },
  '634': { x: 180, y: 30  },
  '645': { x: 300, y: 115 },
  '646': { x: 415, y: 115 },
  '671': { x: 370, y: 220 },
  '680': { x: 510, y: 220 },
  '692': { x: 510, y: 315 },
  '675': { x: 510, y: 405 },
  '684': { x: 370, y: 315 },
  '611': { x: 260, y: 405 },
  '652': { x: 460, y: 405 },
}

// [from, to, style?]
const EDGES = [
  ['650', '632'],
  ['632', '671'],
  ['671', '680'],
  ['632', '633'],
  ['633', '634', 'transformer'],
  ['632', '645'],
  ['645', '646'],
  ['671', '684'],
  ['684', '611'],
  ['684', '652'],
  ['671', '692', 'switch'],
  ['692', '675'],
]

// Map from bus name to PV inverter name (and index into solarScales/cloudCovers).
const PV_BUSES = {
  '675': { name: 'PV675', idx: 0 },
  '680': { name: 'PV680', idx: 1 },
  '611': { name: 'PV611', idx: 2 },
  '652': { name: 'PV652', idx: 3 },
}

function voltageColor(v) {
  if (v === undefined || v === null) return '#4b5563'
  if (v < 0.95 || v > 1.05) return '#f85149'
  if (v < 0.97 || v > 1.03) return '#d29922'
  return '#3fb950'
}

export default function GridGraph({ voltages, violationBuses, selectedPV, onSelectPV }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%' }}>
      {/* Background */}
      <rect width={W} height={H} fill="#0d1117" rx={8} />

      {/* Edges */}
      {EDGES.map(([a, b, style]) => {
        const pa = BUS_POS[a]
        const pb = BUS_POS[b]
        return (
          <line
            key={`${a}-${b}`}
            x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y}
            stroke={style === 'transformer' ? '#58a6ff' : '#30363d'}
            strokeWidth={style ? 1.5 : 2}
            strokeDasharray={style === 'transformer' ? '5 3' : style === 'switch' ? '3 3' : undefined}
          />
        )
      })}

      {/* Bus nodes */}
      {Object.entries(BUS_POS).map(([bus, { x, y }]) => {
        const v    = voltages[bus]
        const col  = voltageColor(v)
        const isPV = bus in PV_BUSES
        const isSrc = bus === '650'
        const pvInfo = PV_BUSES[bus]
        const isSelected = isPV && selectedPV === pvInfo?.name

        return (
          <g
            key={bus}
            transform={`translate(${x},${y})`}
            onClick={() => isPV && onSelectPV(isSelected ? null : pvInfo.name)}
            style={{ cursor: isPV ? 'pointer' : 'default' }}
          >
            {/* Outer glow ring for PV nodes */}
            {isPV && (
              <circle
                r={22}
                fill="none"
                stroke={isSelected ? '#58a6ff' : '#d29922'}
                strokeWidth={isSelected ? 2 : 1.5}
                opacity={0.7}
              />
            )}

            {/* Node body */}
            {isSrc ? (
              <rect
                x={-14} y={-14} width={28} height={28}
                fill="#21262d" stroke="#8b949e" strokeWidth={1.5}
                rx={3}
              />
            ) : (
              <circle
                r={16}
                fill={col + '22'}
                stroke={col}
                strokeWidth={1.5}
              />
            )}

            {/* Bus label */}
            <text
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={isSrc ? 10 : 10}
              fontWeight="600"
              fill={isSrc ? '#8b949e' : col}
            >
              {bus}
            </text>

            {/* Voltage reading below node */}
            {v !== undefined && (
              <text
                y={22}
                textAnchor="middle"
                fontSize={9}
                fill={col}
              >
                {v.toFixed(3)}
              </text>
            )}

            {/* PV label above node */}
            {isPV && (
              <text
                y={-24}
                textAnchor="middle"
                fontSize={9}
                fill="#d29922"
              >
                {pvInfo.name}
              </text>
            )}
          </g>
        )
      })}

      {/* Legend */}
      <g transform={`translate(12, ${H - 62})`}>
        {[
          { col: '#3fb950', label: 'Safe (0.95–1.05 pu)' },
          { col: '#d29922', label: 'Near limit' },
          { col: '#f85149', label: 'Violation' },
        ].map(({ col, label }, i) => (
          <g key={label} transform={`translate(0, ${i * 16})`}>
            <circle r={5} cx={5} cy={0} fill={col} />
            <text x={14} dominantBaseline="central" fontSize={9} fill="#8b949e">
              {label}
            </text>
          </g>
        ))}
      </g>

      {/* Transformer label */}
      <text
        x={(BUS_POS['633'].x + BUS_POS['634'].x) / 2 + 6}
        y={(BUS_POS['633'].y + BUS_POS['634'].y) / 2}
        fontSize={8}
        fill="#58a6ff"
        dominantBaseline="central"
      >
        XFM
      </text>
    </svg>
  )
}
