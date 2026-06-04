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
  if (v === undefined || v === null) return '#9ca3af'
  if (v < 0.95 || v > 1.05) return '#dc2626'
  if (v < 0.97 || v > 1.03) return '#d97706'
  return '#16a34a'
}

export default function GridGraph({ voltages, violationBuses, selectedPV, onSelectPV }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%' }}>
      {/* Background */}
      <rect width={W} height={H} fill="#f8f9fb" rx={8} />

      {/* Edges */}
      {EDGES.map(([a, b, style]) => {
        const pa = BUS_POS[a]
        const pb = BUS_POS[b]
        return (
          <line
            key={`${a}-${b}`}
            x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y}
            stroke={style === 'transformer' ? '#2563eb' : '#9ca3af'}
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
            {/* Outer ring for PV nodes */}
            {isPV && (
              <circle
                r={22}
                fill="none"
                stroke={isSelected ? '#2563eb' : '#d97706'}
                strokeWidth={isSelected ? 2 : 1.5}
                opacity={0.6}
              />
            )}

            {/* Node body */}
            {isSrc ? (
              <rect
                x={-14} y={-14} width={28} height={28}
                fill="#e5e7eb" stroke="#6b7280" strokeWidth={1.5}
                rx={3}
              />
            ) : (
              <circle
                r={16}
                fill={col + '18'}
                stroke={col}
                strokeWidth={1.5}
              />
            )}

            {/* Bus label */}
            <text
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={10}
              fontWeight="700"
              fill={isSrc ? '#6b7280' : col}
            >
              {bus}
            </text>

            {/* Voltage reading below node */}
            {v !== undefined && (
              <text
                y={22}
                textAnchor="middle"
                fontSize={9}
                fontWeight="600"
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
                fontWeight="600"
                fill="#d97706"
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
          { col: '#16a34a', label: 'Safe (0.95–1.05 pu)' },
          { col: '#d97706', label: 'Near limit' },
          { col: '#dc2626', label: 'Violation' },
        ].map(({ col, label }, i) => (
          <g key={label} transform={`translate(0, ${i * 16})`}>
            <circle r={5} cx={5} cy={0} fill={col} />
            <text x={14} dominantBaseline="central" fontSize={9} fill="#6b7280">
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
        fill="#2563eb"
        dominantBaseline="central"
      >
        XFM
      </text>
    </svg>
  )
}
