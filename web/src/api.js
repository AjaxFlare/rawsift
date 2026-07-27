async function request(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || `请求失败 (${response.status})`);
  }
  return payload;
}

export const api = {
  settings: () => request("/api/settings"),
  testProvider: (payload) => request("/api/settings/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  jobs: () => request("/api/jobs"),
  job: (id) => request(`/api/jobs/${id}`),
  analysis: (id) => request(`/api/jobs/${id}/analysis`),
  createJob: (form) => request("/api/jobs", { method: "POST", body: form }),
  review: (id, payload) => request(`/api/jobs/${id}/vision-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
};
