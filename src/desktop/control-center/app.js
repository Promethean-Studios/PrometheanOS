import { getTelemetry } from "./api.js";

const $ = (id) => document.getElementById(id);
const formatMemory = (mb) => typeof mb === "number" ? `${(mb / 1024).toFixed(1)} GB` : "Unavailable";
const available = (value) => value !== null && value !== undefined;
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character]));

function setText(id, value, fallback = "Unavailable") {
  $(id).textContent = available(value) ? value : fallback;
}

function percent(value) {
  return typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
}

function renderWorkloads(ai) {
  const list = $("workload-list");
  const workloads = ai?.workloads || [];
  if (!workloads.length) {
    list.innerHTML = '<div class="empty-state"><span class="empty-icon">⌁</span><strong>No active AI workloads</strong><small>Detected workloads will appear here.</small></div>';
    return;
  }
  list.innerHTML = workloads.map((workload) => `<div class="workload-row"><span class="workload-icon">${escapeHtml((workload.workload || "AI").slice(0, 2).toUpperCase())}</span><span class="workload-name"><strong>${escapeHtml(workload.workload || "Unknown workload")}</strong><small>${escapeHtml(workload.model || workload.name || "Model unavailable")}</small></span><span class="workload-stat">${typeof workload.memory_mb === "number" ? `${workload.memory_mb.toFixed(0)} MB` : "Unavailable"}</span><span class="workload-state">Running</span></div>`).join("");
}

function render(snapshot) {
  const cpu = snapshot.cpu || {};
  const memory = snapshot.memory || {};
  const gpu = snapshot.gpu || {};
  const storage = snapshot.storage || {};
  setText("cpu-value", cpu.model || cpu.architecture);
  setText("cpu-detail", typeof cpu.logical_cores === "number" ? `${cpu.logical_cores} logical cores · ${cpu.load_percent ?? "--"}% load` : "Core data unavailable");
  $("cpu-meter").style.width = `${percent(cpu.load_percent)}%`;
  setText("ram-value", formatMemory(memory.total_mb));
  setText("ram-detail", typeof memory.percent_used === "number" ? `${memory.percent_used.toFixed(0)}% in use` : "Usage unavailable");
  $("ram-meter").style.width = `${percent(memory.percent_used)}%`;
  setText("gpu-value", gpu.name || gpu.model);
  setText("gpu-detail", gpu.status === "available" ? `${gpu.vendor || "GPU"} · ${gpu.utilization_percent ?? "--"}% utilization` : "GPU unavailable");
  setText("vram-value", formatMemory(gpu.vram_mb));
  setText("vram-detail", typeof gpu.vram_used_mb === "number" ? `${formatMemory(gpu.vram_used_mb)} in use` : "Usage unavailable");
  $("vram-meter").style.width = `${gpu.vram_mb && gpu.vram_used_mb ? percent(gpu.vram_used_mb / gpu.vram_mb * 100) : 0}%`;
  const used = typeof storage.percent_used === "number" ? storage.percent_used : null;
  setText("storage-percent", used === null ? null : `${used.toFixed(0)}%`);
  $("storage-ring").style.setProperty("--usage", `${used || 0}%`);
  setText("storage-models", storage.total_gb ? `${storage.used_gb?.toFixed(1) || "--"} / ${storage.total_gb.toFixed(1)} GB` : null);
  setText("storage-free", storage.free_gb ? `${storage.free_gb.toFixed(1)} GB` : null);
  const active = snapshot.network?.active_interfaces || [];
  setText("network-detail", active.length ? `${active.length} active interface${active.length === 1 ? "" : "s"}` : "No active interfaces reported");
  setText("network-state", active.length ? "Connected" : "Unavailable");
  renderWorkloads(snapshot.ai);
  setText("updated-at", snapshot.timestamp ? `Last updated: ${new Date(snapshot.timestamp).toLocaleTimeString()}` : "Last updated: unavailable");
}

async function refresh() {
  $("connection-status").textContent = "Refreshing";
  try { render(await getTelemetry()); $("connection-status").textContent = "Connected"; }
  catch (error) { $("connection-status").textContent = "API unavailable"; $("updated-at").textContent = "Last updated: unavailable"; }
}

$("refresh-button").addEventListener("click", refresh);
$("theme-toggle").addEventListener("click", () => {
  document.documentElement.classList.toggle("light");
  $("theme-toggle").querySelector("span:last-child").textContent = document.documentElement.classList.contains("light") ? "Dark" : "Light";
});
$("low-end-toggle").addEventListener("change", (event) => document.documentElement.classList.toggle("low-end", event.target.checked));
refresh();