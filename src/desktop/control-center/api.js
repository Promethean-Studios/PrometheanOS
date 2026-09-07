const API_ROOT = "";

export async function getTelemetry() {
  const response = await fetch(`${API_ROOT}/telemetry`, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new Error(`Telemetry request failed: ${response.status}`);
  return response.json();
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Accept: "application/json", ...(options.headers || {}) } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

export async function searchModels(query) {
  return requestJson(`/models?search=${encodeURIComponent(query)}&limit=20`);
}

export async function getInstalledModels() {
  return requestJson("/models");
}

export async function startModelDownload(repositoryId, filename, sizeBytes) {
  return requestJson("/models/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repository_id: repositoryId, filename, size_bytes: sizeBytes }) });
}

export async function getDownloadStatus(jobId) {
  return requestJson(`/models/download/${encodeURIComponent(jobId)}`);
}

export async function cancelModelDownload(jobId) {
  return requestJson("/models/download/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: jobId }) });
}

export async function deleteInstalledModel(path) {
  return requestJson(`/models/installed?path=${encodeURIComponent(path)}`, { method: "DELETE" });
}