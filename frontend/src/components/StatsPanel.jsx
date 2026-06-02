export default function StatsPanel({ result }) {
  if (!result) {
    return (
      <div className="control-section">
        <div className="section-title">Metrics</div>
        <div style={{ color: '#8b949e', fontSize: 11 }}>Waiting for simulation…</div>
      </div>
    )
  }

  const { n_violations, losses_kw, reward, violation_buses, pv_kvar } = result
  const violClass = n_violations === 0 ? 'ok' : n_violations <= 2 ? 'warn' : 'bad'

  return (
    <div className="control-section">
      <div className="section-title">Metrics</div>

      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-label">Violations</div>
          <div className={`stat-value ${violClass}`}>{n_violations}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Losses</div>
          <div className="stat-value">{losses_kw.toFixed(1)}<span style={{ fontSize: 10, color: '#8b949e' }}> kW</span></div>
        </div>
        <div className="stat-box" style={{ gridColumn: 'span 2' }}>
          <div className="stat-label">Reward</div>
          <div className={`stat-value ${reward >= -0.5 ? 'ok' : reward >= -2 ? 'warn' : 'bad'}`}>
            {reward.toFixed(4)}
          </div>
        </div>
      </div>

      {violation_buses.length > 0 && (
        <div className="violation-list">
          Violation buses: {violation_buses.join(', ')}
        </div>
      )}

      {/* Reactive power setpoints */}
      {pv_kvar && (
        <div style={{ marginTop: 10 }}>
          <div className="section-title" style={{ marginBottom: 6 }}>Agent kVAR Setpoints</div>
          {Object.entries(pv_kvar).map(([pv, q]) => (
            <div key={pv} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
              <span style={{ color: '#8b949e' }}>{pv}</span>
              <span style={{ color: q > 0 ? '#3fb950' : q < 0 ? '#f85149' : '#8b949e', fontWeight: 600 }}>
                {q >= 0 ? '+' : ''}{q.toFixed(0)} kVAR
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
