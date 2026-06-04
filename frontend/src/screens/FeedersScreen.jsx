import GridPreview from '../components/GridPreview.jsx'

const POLICY_COLORS = {
  lag_sac_both:       '#3b82f6',
  lag_sac_curriculum: '#6366f1',
  sac_both:           '#8b5cf6',
  sac_none:           '#a78bfa',
  droop:              '#6b7280',
  zero:               '#9ca3af',
}

const POLICY_SHORT = {
  lag_sac_both:       'Lag-SAC+DR',
  lag_sac_curriculum: 'Lag-SAC+Curr',
  sac_both:           'SAC+DR',
  sac_none:           'SAC',
  droop:              'Droop',
  zero:               'Zero',
}

export default function FeedersScreen({ grids, onSelect }) {
  if (!grids) {
    return (
      <div className="feeders-loading">
        <div className="feeders-loading-dot" />
        Loading feeders…
      </div>
    )
  }

  return (
    <div className="feeders-screen">
      <header className="feeders-header">
        <div>
          <h1 className="feeders-title">VoltVAR Explorer</h1>
          <p className="feeders-subtitle">
            Select a distribution feeder to explore RL-based Volt-VAR control
          </p>
        </div>
      </header>

      <div className="feeders-grid">
        {grids.map(grid => (
          <button key={grid.id} className="feeder-card" onClick={() => onSelect(grid)}>
            {/* Topology preview */}
            <div className="feeder-card-preview">
              <GridPreview grid={grid} />
            </div>

            {/* Metadata */}
            <div className="feeder-card-body">
              <div className="feeder-card-top">
                <span className="feeder-card-name">{grid.name}</span>
                <span className="feeder-card-voltage">{grid.voltage_kv} kV</span>
              </div>

              <div className="feeder-card-stats">
                <span>{grid.n_buses} buses</span>
                <span className="stat-sep">·</span>
                <span>{grid.n_pv} inverters</span>
                <span className="stat-sep">·</span>
                <span>{grid.available_models.length} policies</span>
              </div>

              <p className="feeder-card-desc">{grid.description}</p>

              <div className="feeder-card-models">
                {grid.available_models.map(m => (
                  <span
                    key={m}
                    className="model-badge"
                    style={{ background: (POLICY_COLORS[m] || '#6b7280') + '22',
                             color:      POLICY_COLORS[m] || '#6b7280',
                             borderColor:(POLICY_COLORS[m] || '#6b7280') + '55' }}
                  >
                    {POLICY_SHORT[m] || m}
                  </span>
                ))}
              </div>
            </div>

            <div className="feeder-card-arrow">→</div>
          </button>
        ))}
      </div>
    </div>
  )
}
