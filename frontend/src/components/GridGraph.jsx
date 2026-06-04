const W = 620
const H = 440

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

const PV_BUSES = {
  '675': { name: 'PV675', idx: 0 },
  '680': { name: 'PV680', idx: 1 },
  '611': { name: 'PV611', idx: 2 },
  '652': { name: 'PV652', idx: 3 },
}

function voltageColor(v) {
  if (v === undefined || v === null) return '#3d4454'
  if (v < 0.95 || v > 1.05) return '#f85149'
  if (v < 0.97 || v > 1.03) return '#d29922'
  return '#3fb950'
}

export default function GridGraph({ voltages, violationBuses, selectedPV, onSelectPV }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%' }}>
      <defs>
        <radialGradient id="bg-grad" cx="50%" cy="45%" r="65%">
          <stop offset="0%" stopColor="#161b22" />
          <stop offset="100%" stopColor="#0d1117" />
        </radialGradient>
        <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="12" cy="12" r="0.75" fill="#1c2333" />
        </pattern>
      </defs>

      {/* Background */}
      <rect width={W} height={H} fill="url(#bg-grad)" rx={8} />
      <rect width={W} height={H} fill="url(#dots)" rx={8} />

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
        const v       = voltages[bus]
        const col     = voltageColor(v)
        const isPV    = bus in PV_BUSES
        const isSrc   = bus === '650'
        const pvInfo  = PV_BUSES[bus]
        const isSelected = isPV && selectedPV === pvInfo?.name

        return (
          <g
            key={bus}
            transform={`translate(${x},${y})`}
            onClick={() => isPV && onSelectPV(isSelected ? null : pvInfo.name)}
            style={{ cursor: isPV ? 'pointer' : 'default' }}
          >
            {isPV && (
              <circle
                r={22}
                fill="none"
                stroke={isSelected ? '#58a6ff' : '#d29922'}
                strokeWidth={isSelected ? 2 : 1.5}
                opacity={0.5}
              />
            )}

            {isSrc ? (
              <rect
                x={-14} y={-14} width={28} height={28}
                fill="#1e2535" stroke="#8b949e" strokeWidth={1.5}
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

            <text
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={10}
              fontWeight="600"
              fill={isSrc ? '#8b949e' : col}
            >
              {bus}
            </text>

            {v !== undefined && (
              <text
                y={22}
                textAnchor="middle"
                fontSize={9}
                fontWeight="500"
                fill={col}
              >
                {v.toFixed(3)}
              </text>
            )}

            {isPV && (
              <text
                y={-25}
                textAnchor="middle"
                fontSize={9}
                fontWeight="500"
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
