/**
 * Full interactive SVG of a distribution feeder.
 * Entirely data-driven — no hardcoded positions or topology.
 */

function voltageColor(v) {
  if (v === undefined || v === null) return 'var(--muted)'
  if (v < 0.95 || v > 1.05) return 'var(--red)'
  if (v < 0.97 || v > 1.03) return 'var(--yellow)'
  return 'var(--green)'
}

export default function GridGraph({ grid, voltages, selectedPV, onSelectPV }) {
  if (!grid?.node_positions) return null

  const { node_positions, edges, source_bus, pv_buses } = grid
  const pvBusMap = {}  // {bus: {name, idx}}
  Object.entries(pv_buses || {}).forEach(([name, bus], idx) => {
    pvBusMap[bus] = { name, idx }
  })

  // Compute viewBox from node positions
  const positions = Object.values(node_positions)
  const xs = positions.map(p => p.x)
  const ys = positions.map(p => p.y)
  const pad = 36
  const W = Math.max(...xs) + pad * 2
  const H = Math.max(...ys) + pad * 2

  const nodeR = grid.n_buses <= 13 ? 16 : 10
  const fontSize = grid.n_buses <= 13 ? 10 : 8

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: '100%' }}>
      <defs>
        <pattern id="gp-main" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--border)" strokeWidth="0.5" />
        </pattern>
        <pattern id="gp-major" width="100" height="100" patternUnits="userSpaceOnUse">
          <rect width="100" height="100" fill="url(#gp-main)" />
          <path d="M 100 0 L 0 0 0 100" fill="none" stroke="var(--border)" strokeWidth="1" opacity="0.6" />
        </pattern>
      </defs>

      <rect width={W} height={H} fill="var(--bg)" rx={8} />
      <rect width={W} height={H} fill="url(#gp-major)" rx={8} />

      {/* Edges */}
      {edges.map(([a, b, style]) => {
        const pa = node_positions[a], pb = node_positions[b]
        if (!pa || !pb) return null
        return (
          <line
            key={`${a}-${b}`}
            x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y}
            stroke={style === 'transformer' ? 'var(--accent)' : 'var(--border)'}
            strokeWidth={style ? 1.5 : 2}
            strokeDasharray={
              style === 'transformer' ? '5 3' :
              style === 'switch'      ? '3 3' : undefined
            }
          />
        )
      })}

      {/* Nodes */}
      {Object.entries(node_positions).map(([bus, { x, y }]) => {
        const v      = voltages?.[bus]
        const col    = voltageColor(v)
        const isSrc  = bus === source_bus
        const pvInfo = pvBusMap[bus]
        const isPV   = !!pvInfo
        const isSelected = isPV && selectedPV === pvInfo.name

        return (
          <g
            key={bus}
            transform={`translate(${x},${y})`}
            onClick={() => isPV && onSelectPV?.(isSelected ? null : pvInfo.name)}
            style={{ cursor: isPV ? 'pointer' : 'default' }}
          >
            {isPV && (
              <circle
                r={nodeR + 6}
                fill="none"
                stroke={isSelected ? 'var(--accent)' : 'var(--yellow)'}
                strokeWidth={isSelected ? 2 : 1.5}
                opacity={0.65}
              />
            )}

            {isSrc ? (
              <rect
                x={-nodeR + 2} y={-nodeR + 2}
                width={(nodeR - 2) * 2} height={(nodeR - 2) * 2}
                fill="var(--surface)" stroke="var(--muted)" strokeWidth={1.5} rx={3}
              />
            ) : (
              <circle r={nodeR} fill={col + '18'} stroke={col} strokeWidth={1.5} />
            )}

            <text
              textAnchor="middle" dominantBaseline="central"
              fontSize={fontSize} fontWeight="700"
              fill={isSrc ? 'var(--muted)' : col}
            >
              {bus}
            </text>

            {v !== undefined && (
              <text y={nodeR + 10} textAnchor="middle" fontSize={fontSize - 1} fontWeight="600" fill={col}>
                {v.toFixed(3)}
              </text>
            )}

            {isPV && (
              <text y={-(nodeR + 10)} textAnchor="middle" fontSize={fontSize - 1} fontWeight="600" fill="var(--yellow)">
                {pvInfo.name}
              </text>
            )}
          </g>
        )
      })}

      {/* Legend */}
      <g transform={`translate(10, ${H - 58})`}>
        {[
          { col: 'var(--green)',  label: 'Safe (0.95–1.05 pu)' },
          { col: 'var(--yellow)', label: 'Near limit' },
          { col: 'var(--red)',    label: 'Violation' },
        ].map(({ col, label }, i) => (
          <g key={label} transform={`translate(0, ${i * 16})`}>
            <circle r={4} cx={4} cy={0} fill={col} />
            <text x={12} dominantBaseline="central" fontSize={8} fill="var(--muted)">{label}</text>
          </g>
        ))}
      </g>
    </svg>
  )
}
