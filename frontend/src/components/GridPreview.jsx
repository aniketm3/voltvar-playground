/**
 * Compact topology-only SVG used inside feeder selection cards.
 * No labels, no voltage colours — just structure.
 */
export default function GridPreview({ grid }) {
  const { node_positions, edges, source_bus, pv_buses } = grid
  if (!node_positions) return null

  const positions = Object.values(node_positions)
  const xs = positions.map(p => p.x)
  const ys = positions.map(p => p.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const pad = 16
  const W = maxX - minX + pad * 2
  const H = maxY - minY + pad * 2

  const px = x => x - minX + pad
  const py = y => y - minY + pad

  const pvBusSet = new Set(Object.values(pv_buses || {}))

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: '100%' }}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Graph-paper pattern */}
      <defs>
        <pattern id={`gp-${grid.id}`} width="14" height="14" patternUnits="userSpaceOnUse">
          <path d="M 14 0 L 0 0 0 14" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.15" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill={`url(#gp-${grid.id})`} />

      {/* Edges */}
      {edges.map(([a, b, style]) => {
        const pa = node_positions[a], pb = node_positions[b]
        if (!pa || !pb) return null
        return (
          <line
            key={`${a}-${b}`}
            x1={px(pa.x)} y1={py(pa.y)}
            x2={px(pb.x)} y2={py(pb.y)}
            stroke={style === 'transformer' ? 'var(--accent)' : 'currentColor'}
            strokeWidth={1.5}
            opacity={0.35}
            strokeDasharray={style === 'transformer' ? '3 2' : style === 'switch' ? '2 2' : undefined}
          />
        )
      })}

      {/* Nodes */}
      {Object.entries(node_positions).map(([bus, { x, y }]) => {
        const isSrc = bus === source_bus
        const isPV  = pvBusSet.has(bus)
        return (
          <g key={bus} transform={`translate(${px(x)},${py(y)})`}>
            {isPV && <circle r={7} fill="none" stroke="var(--yellow)" strokeWidth={1.2} opacity={0.7} />}
            <circle
              r={isSrc ? 5 : 4}
              fill={isSrc ? 'var(--muted)' : isPV ? 'var(--yellow)' : 'var(--accent)'}
              opacity={0.8}
            />
          </g>
        )
      })}
    </svg>
  )
}
