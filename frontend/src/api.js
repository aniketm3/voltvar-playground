const BASE = 'http://localhost:8000'

export async function getGrids() {
  const res = await fetch(`${BASE}/grids`)
  if (!res.ok) throw new Error(`/grids failed: ${res.status}`)
  return res.json()
}

export async function simulateStep({ gridId, policy, timestep, solarScales, cloudCovers, loadScale }) {
  const res = await fetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grid_id:      gridId,
      policy,
      mode:         'single_step',
      timestep,
      solar_scales: solarScales,
      cloud_covers: cloudCovers,
      load_scale:   loadScale,
    }),
  })
  if (!res.ok) throw new Error(`simulate failed: ${res.status}`)
  return res.json()
}

export async function simulateEpisode({ gridId, policy, solarScales, cloudCovers, loadScale }) {
  const res = await fetch(`${BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grid_id:      gridId,
      policy,
      mode:         'full_episode',
      timestep:     0,
      solar_scales: solarScales,
      cloud_covers: cloudCovers,
      load_scale:   loadScale,
    }),
  })
  if (!res.ok) throw new Error(`simulate_episode failed: ${res.status}`)
  return res.json()
}
