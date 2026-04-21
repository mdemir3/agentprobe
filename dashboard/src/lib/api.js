const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Targets
  listTargets: () => request('/targets/'),
  getTarget: (id) => request(`/targets/${id}`),
  registerTarget: (data) => request('/targets/', { method: 'POST', body: JSON.stringify(data) }),
  deleteTarget: (id) => request(`/targets/${id}`, { method: 'DELETE' }),

  // Plans
  listPlans: (targetId) => request(`/plans/${targetId ? `?target_id=${targetId}` : ''}`),
  getPlan: (id) => request(`/plans/${id}`),
  createPlan: (data) => request('/plans/', { method: 'POST', body: JSON.stringify(data) }),

  // Runs
  listRuns: (targetId) => request(`/runs/${targetId ? `?target_id=${targetId}` : ''}`),
  getRun: (id) => request(`/runs/${id}`),
  startRun: (data) => request('/runs/', { method: 'POST', body: JSON.stringify(data) }),

  // Reports
  listReports: (targetId) => request(`/reports/${targetId ? `?target_id=${targetId}` : ''}`),
  getReport: (id) => request(`/reports/${id}`),
  generateReport: (runId) => request(`/reports/${runId}`, { method: 'POST' }),
};
