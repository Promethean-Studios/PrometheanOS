import { cancelModelDownload, deleteInstalledModel, getDownloadStatus, getInstalledModels, getTelemetry, searchModels, startModelDownload } from "./api.js";

const $ = (id) => document.getElementById(id);
const formatMemory = (mb) => typeof mb === "number" && Number.isFinite(mb) ? `${(mb / 1024).toFixed(1)} GB` : "Unavailable";
const formatRate = (bytes) => typeof bytes === "number" ? `${(bytes / 1024).toFixed(1)} KB/s` : "Unavailable";
const formatDuration = (seconds) => typeof seconds === "number" ? `${Math.floor(seconds / 86400)}d ${Math.floor(seconds / 3600) % 24}h ${Math.floor(seconds / 60) % 60}m` : "Unavailable";
const formatBytes = (bytes) => typeof bytes === "number" ? (bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(0)} MB`) : "Size unavailable";
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
  setText("cpu-detail", typeof cpu.logical_cores === "number" ? `${cpu.physical_cores ?? "--"} cores · ${cpu.logical_cores} threads · ${cpu.load_percent ?? "--"}% load` : "Core data unavailable");
  setText("cpu-temperature", typeof cpu.temperature_c === "number" ? `${cpu.temperature_c.toFixed(1)} °C` : null);
  $("cpu-meter").style.width = `${percent(cpu.load_percent)}%`;
  setText("ram-value", formatMemory(memory.total_mb));
  setText("ram-detail", typeof memory.percent_used === "number" ? `${memory.percent_used.toFixed(0)}% in use · ${formatMemory(memory.used_mb)} used` : "Usage unavailable");
  setText("ram-free", formatMemory(memory.available_mb));
  $("ram-meter").style.width = `${percent(memory.percent_used)}%`;
  setText("gpu-value", gpu.name && gpu.name !== "no-gpu" ? gpu.name : gpu.model);
  setText("gpu-detail", gpu.status === "available" ? `${gpu.vendor || "GPU"}${gpu.gpus?.length > 1 ? ` · ${gpu.gpus.length} devices` : ""} · ${gpu.utilization_percent ?? "--"}% utilization · ${gpu.temperature_c ?? "--"} °C` : "GPU unavailable");
  setText("vram-value", formatMemory(gpu.vram_mb));
  setText("vram-detail", typeof gpu.vram_used_mb === "number" ? `${formatMemory(gpu.vram_used_mb)} in use` : "Usage unavailable");
  $("vram-meter").style.width = `${gpu.vram_mb && gpu.vram_used_mb ? percent(gpu.vram_used_mb / gpu.vram_mb * 100) : 0}%`;
  const used = typeof storage.percent_used === "number" ? storage.percent_used : null;
  setText("storage-percent", used === null ? null : `${used.toFixed(0)}%`);
  $("storage-ring").style.setProperty("--usage", `${used || 0}%`);
  setText("storage-models", storage.total_gb ? `${storage.used_gb?.toFixed(1) || "--"} / ${storage.total_gb.toFixed(1)} GB` : null);
  setText("storage-free", typeof storage.free_gb === "number" ? `${storage.free_gb.toFixed(1)} GB` : null);
  renderDisks(storage.disks || []);
  const active = snapshot.network?.active_interfaces || [];
  setText("network-detail", active.length ? `${active.length} active interface${active.length === 1 ? "" : "s"}` : "No active interfaces reported");
  setText("network-state", active.length ? "Connected" : "Unavailable");
  renderNetwork(snapshot.network?.interfaces || {});
  setText("uptime", formatDuration(snapshot.system?.uptime_seconds));
  const power = snapshot.power || {};
  setText("power-value", power.available ? `${power.percent ?? "--"}%` : null);
  setText("power-detail", power.available ? (power.plugged_in ? "Plugged in" : "On battery") : "Battery unavailable");
  renderWorkloads(snapshot.ai);
  setText("updated-at", snapshot.timestamp ? `Last updated: ${new Date(snapshot.timestamp).toLocaleTimeString()}` : "Last updated: unavailable");
}

function renderDisks(disks) {
  $("disk-list").innerHTML = disks.length ? disks.map((disk) => `<div class="data-row"><span>${escapeHtml(disk.mount_point || disk.device || "Disk")}</span><strong>${formatMemory(disk.capacity_gb * 1024)} total</strong><small>${formatMemory(disk.used_gb * 1024)} used · ${formatMemory(disk.available_gb * 1024)} free</small></div>`).join("") : '<div class="empty-state">Storage unavailable</div>';
}

function renderNetwork(interfaces) {
  const rows = Object.entries(interfaces).filter(([, item]) => item.active);
  $("interface-list").innerHTML = rows.length ? rows.map(([name, item]) => `<div class="data-row"><span>${escapeHtml(name)}</span><strong>↓ ${formatRate(item.download_bytes_per_second)} · ↑ ${formatRate(item.upload_bytes_per_second)}</strong><small>${escapeHtml((item.addresses || []).join(", ") || "Address unavailable")}</small></div>`).join("") : '<div class="empty-state">Network activity unavailable</div>';
}

function renderModelResults(models) {
  const list = $("model-results");
  list.innerHTML = models.length ? models.map((model) => {
    const compatibility = model.compatibility || {};
    const files = (model.files || []).filter((file) => /\.(gguf|ggml|safetensors|bin|pt|onnx|pth)$/i.test(file.filename));
    const file = files[0];
    return `<article class="model-row"><div class="model-info"><strong>${escapeHtml(model.name || "Unnamed model")}</strong><small>${escapeHtml(model.author || "Author unavailable")} · ${escapeHtml(model.description || model.model_format || "Hugging Face model")}</small><span>${escapeHtml(model.quantization || "Quantization unavailable")} · ${formatBytes(model.download_size_bytes)} · ${compatibility.estimated_required_mb ? `~${formatBytes(compatibility.estimated_required_mb * 1024 ** 2)} RAM` : "RAM estimate unavailable"}</span></div><span class="compatibility ${escapeHtml((compatibility.category || "Unsupported").toLowerCase().replaceAll(" ", "-"))}">${escapeHtml(compatibility.category || "Unsupported")}</span>${file ? `<button class="model-download" data-repo="${escapeHtml(model.repository_id || model.name)}" data-file="${escapeHtml(file.filename)}" data-size="${file.size_bytes || ""}">Download ${escapeHtml(file.filename)}</button>` : "<small class=\"muted-value\">No downloadable model file listed</small>"}</article>`;
  }).join("") : '<div class="empty-state">No remote models found.</div>';
}

function renderInstalled(models) {
  $("installed-models").innerHTML = models.length ? models.map((model) => `<div class="model-row"><div class="model-info"><strong>${escapeHtml(model.name)}</strong><small>${escapeHtml(model.filename)} · ${formatBytes(model.size_bytes)} · ${escapeHtml(model.format || "format unavailable")}</small></div><button class="model-delete" data-path="${escapeHtml(model.path)}">Delete</button></div>`).join("") : '<div class="empty-state">No installed model files found.</div>';
}

async function refreshInstalled() {
  try { renderInstalled((await getInstalledModels()).models || []); } catch (error) { $("installed-models").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`; }
}

async function searchForModels(query) {
  if (!query.trim()) return;
  $("model-status").textContent = "Searching Hugging Face...";
  try {
    const models = (await searchModels(query.trim())).models || [];
    renderModelResults(models);
    $("model-status").textContent = `${models.length} real model result${models.length === 1 ? "" : "s"}`;
  } catch (error) { $("model-status").textContent = `Search failed: ${error.message}`; }
}

async function downloadModel(button) {
  button.disabled = true;
  try {
    const result = await startModelDownload(button.dataset.repo, button.dataset.file, button.dataset.size ? Number(button.dataset.size) : null);
    if (result.job_id) {
      $("download-list").insertAdjacentHTML("afterbegin", `<div class="download-row" data-job="${escapeHtml(result.job_id)}"><span>${escapeHtml(button.dataset.file)}</span><progress max="100" value="0"></progress><button class="download-cancel" data-job="${escapeHtml(result.job_id)}">Cancel</button><small>Queued</small></div>`);
      pollDownload(result.job_id);
    } else { $("model-status").textContent = result.status === "already_installed" ? "That model file is already installed." : result.error || "Download was not started."; }
  } catch (error) { $("model-status").textContent = `Download failed: ${error.message}`; }
  button.disabled = false;
}

async function pollDownload(jobId) {
  try {
    const status = await getDownloadStatus(jobId);
    const row = document.querySelector(`[data-job="${CSS.escape(jobId)}"]`);
    if (!row) return;
    row.querySelector("progress").value = status.progress_percent || 0;
    row.querySelector("small").textContent = status.status === "downloading" ? `${status.progress_percent ?? 0}% · ${formatBytes(status.downloaded_bytes)}` : status.error || status.status;
    if (["completed", "failed", "cancelled"].includes(status.status)) { if (status.status === "completed") refreshInstalled(); return; }
    setTimeout(() => pollDownload(jobId), 500);
  } catch (error) { $("model-status").textContent = `Download status unavailable: ${error.message}`; }
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
$("model-search-form").addEventListener("submit", (event) => { event.preventDefault(); searchForModels($("model-search-input").value); });
$("installed-refresh").addEventListener("click", refreshInstalled);
$("model-results").addEventListener("click", (event) => { const button = event.target.closest(".model-download"); if (button) downloadModel(button); });
$("installed-models").addEventListener("click", async (event) => { const button = event.target.closest(".model-delete"); if (!button) return; if (window.confirm(`Delete ${button.dataset.path}?`)) { await deleteInstalledModel(button.dataset.path); refreshInstalled(); } });
$("download-list").addEventListener("click", async (event) => { const button = event.target.closest(".download-cancel"); if (button) await cancelModelDownload(button.dataset.job); });
refresh();
refreshInstalled();
setInterval(refresh, 2000);