const API_ROOT = "";

export async function getTelemetry() {
  const response = await fetch(`${API_ROOT}/telemetry`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Telemetry request failed: ${response.status}`);
  return response.json();
}