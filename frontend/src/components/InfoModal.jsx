export default function InfoModal({ onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>About VoltVAR Explorer</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <Section title="What is this?">
            A 4.16 kV power distribution grid serves homes and businesses across 13 buses.
            When rooftop solar panels generate power, voltages can spike above safe limits.
            <em> Volt-VAR control</em> uses the reactive power capability of solar inverters
            to nudge voltages back into the safe band — without wasting real power.
          </Section>

          <Section title="The RL agent">
            A Soft Actor-Critic (SAC) agent was trained via reinforcement learning to control
            4 PV inverters on the IEEE 13-bus feeder. At each 15-minute step it observes all
            12 bus voltages, the active power each inverter is producing, and the time of day.
            It then chooses how many kVAR each inverter should absorb (−) or inject (+).
            The agent was trained with <strong>domain randomization</strong> over line
            impedances, capacitor ratings, and solar/load variability — making it robust to
            conditions it hasn't seen before.
          </Section>

          <Section title="Voltages &amp; violations">
            Each bus voltage should stay between <strong>0.95 pu</strong> and <strong>1.05 pu</strong> (per-unit,
            where 1.0 = nominal). Outside that band is a <span style={{color:'#dc2626'}}>violation</span> — a
            potential equipment-protection or power-quality issue. Buses are color-coded:
            <ul>
              <li><span style={{color:'#16a34a'}}>●</span> Green — safely within 0.95–1.05</li>
              <li><span style={{color:'#d97706'}}>●</span> Yellow — within 2% of a limit</li>
              <li><span style={{color:'#dc2626'}}>●</span> Red — violation</li>
            </ul>
          </Section>

          <Section title="Sliders">
            <ul>
              <li><strong>Time of day</strong> — scrubs through a 24-hour episode (96 × 15-min steps). Solar output peaks at noon.</li>
              <li><strong>Load scale</strong> — multiplies the baseline residential demand. 1.0 = typical day. 1.5 = heat wave peak.</li>
              <li><strong>Solar scale</strong> — scales how much sun each inverter's panels receive relative to clear-sky rated output. 1.0 = full sun, 0 = no panels.</li>
              <li><strong>Cloud cover</strong> — fraction of sunlight blocked by clouds at this moment. 0% = clear sky, 100% = fully overcast. The 24-hour sparkline shows the combined effect on that inverter's output across the full day.</li>
            </ul>
          </Section>

          <Section title="Policies">
            <ul>
              <li><strong>Lag-SAC + domain-rand ★</strong> — Lagrangian-constrained SAC trained with full domain randomization. The Lagrange multiplier explicitly penalizes voltage violations as a hard constraint, making it both safer and more efficient than unconstrained SAC.</li>
              <li><strong>Lag-SAC + curriculum</strong> — same constrained objective but trained with curriculum learning, starting easy and progressively widening the domain.</li>
              <li><strong>SAC + domain-rand</strong> — unconstrained SAC with domain randomization. Minimizes a weighted sum of violations and losses but has no hard safety guarantee.</li>
              <li><strong>SAC (no DR)</strong> — unconstrained SAC on fixed conditions. Struggles when pushed outside its training distribution.</li>
              <li><strong>Droop (IEEE 1547)</strong> — rule-based controller with a piecewise-linear volt-VAR curve. Zero violations but over-conservative: absorbs maximum VARs and drives losses up.</li>
              <li><strong>Zero VAR</strong> — no reactive power control. Shows what happens without any VVC.</li>
            </ul>
          </Section>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="modal-section">
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  )
}
