const $ = (id) => document.getElementById(id);
const steps = ["welcome", "language", "network", "user", "hardware", "ai", "models", "finish"];
const labels = ["Welcome", "Language", "Network", "User", "Hardware", "AI setup", "Models", "Finish"];
let snapshot;
let index = 0;

const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character]));
const formatMemory = (mb) => typeof mb === "number" ? `${(mb / 1024).toFixed(1)} GB` : "Unavailable";
const formatStorage = (gb) => typeof gb === "number" ? `${gb.toFixed(1)} GB free` : "Unavailable";

async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Accept: "application/json", ...(options.headers || {}) } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

function renderRail() {
  $("step-list").innerHTML = labels.map((label, stepIndex) => `<li class="${stepIndex === index ? "active" : ""} ${stepIndex < index ? "complete" : ""}"><span>${stepIndex + 1}</span>${label}</li>`).join("");
  $("step-count").textContent = `Step ${index + 1} of ${steps.length}`;
}

function renderNetwork() {
  const interfaces = snapshot?.hardware?.network?.interfaces || {};
  const entries = Object.entries(interfaces);
  $("network-options").innerHTML = entries.length ? entries.map(([name, item], itemIndex) => `<label class="choice-card"><input type="radio" name="network_interface" value="${escapeHtml(name)}" ${item.active ? "checked" : ""}><span><strong>${escapeHtml(name)}${itemIndex === 0 && item.active ? " · active" : ""}</strong><small>${escapeHtml((item.addresses || []).join(", ") || "Address unavailable")}</small></span></label>`).join("") : "<div class=\"empty-card\">No network interfaces reported</div>";
  $("network-options").insertAdjacentHTML("beforeend", '<label class="choice-card"><input type="radio" name="network_interface" value="offline" checked><span><strong>Continue offline</strong><small>Network configuration can be revisited later.</small></span></label>');
  $("network-note").textContent = entries.length ? "Choose an interface or continue offline." : "No interface information is available; continuing offline is fine.";
}

function renderHardware() {
  const hardware = snapshot?.hardware || {};
  const cpu = hardware.cpu || {};
  const memory = hardware.memory || {};
  const storage = hardware.storage || {};
  const gpu = hardware.gpu || {};
  const gpuNames = (gpu.gpus || []).map((item) => item.name || item.model).filter(Boolean);
  const cards = [["CPU", cpu.model || cpu.architecture || "Unavailable", `${cpu.physical_cores ?? "--"} cores · ${cpu.logical_cores ?? "--"} threads`], ["Memory", formatMemory(memory.total_mb), `${formatMemory(memory.available_mb)} available`], ["GPU", gpuNames.length ? gpuNames.join(", ") : "Unavailable", gpu.status === "available" ? `${gpu.vendor || "GPU"} detected` : "No supported GPU detected"], ["Storage", formatStorage(storage.free_gb), storage.mount_point || "System storage"]];
  $("hardware-grid").innerHTML = cards.map(([title, value, detail]) => `<div class="hardware-card"><small>${title}</small><strong>${escapeHtml(value)}</strong><span>${escapeHtml(detail)}</span></div>`).join("");
  const runtimes = snapshot?.hardware?.ai?.runtimes || snapshot?.ai?.runtimes || snapshot?.hardware?.capabilities?.runtimes || {};
  $("runtime-list").innerHTML = Object.keys(runtimes).length ? `<p class="eyebrow">Detected runtimes</p><p class="runtime-values">${Object.entries(runtimes).filter(([, value]) => value === "AVAILABLE").map(([name]) => escapeHtml(name)).join(" · ") || "No optional runtimes detected"}</p>` : "";
}

function renderRecommendations() {
  const models = snapshot?.recommendations || [];
  $("recommendation-list").innerHTML = models.length ? models.map((model) => `<article class="recommendation"><div><strong>${escapeHtml(model.name)}</strong><small>${escapeHtml(model.model_format)} · ${escapeHtml(model.quantization)} · ${(model.parameter_count / 1e9).toFixed(1)}B parameters</small></div><span class="compatibility ${(model.compatibility.category || "Unsupported").toLowerCase().replaceAll(" ", "-")}">${escapeHtml(model.compatibility.category || "Unsupported")}</span><small>${escapeHtml(model.compatibility.reason || "Estimate unavailable")}</small></article>`).join("") : '<div class="empty-card">Recommendations unavailable offline.</div>';
}

function renderFinish() {
  const state = snapshot?.state || {};
  const name = state.user?.display_name || "operator";
  $("finish-summary").innerHTML = `<strong>Welcome, ${escapeHtml(name)}.</strong><span>${state.language || "en_US"} · ${state.keyboard || "us"} keyboard · ${state.ai?.skipped ? "AI setup skipped" : "AI setup prepared"}</span>`;
}

function render() {
  renderRail();
  document.querySelectorAll(".step-panel").forEach((panel) => { panel.hidden = panel.dataset.step !== steps[index]; });
  $("back-button").disabled = index === 0;
  $("next-button").textContent = index === steps.length - 1 ? "Finish setup" : "Continue";
  if (steps[index] === "network") renderNetwork();
  if (steps[index] === "hardware" || steps[index] === "ai") renderHardware();
  if (steps[index] === "models") renderRecommendations();
  if (steps[index] === "finish") renderFinish();
  document.querySelector(".step-panel:not([hidden]) h1")?.focus();
}

function collect() {
  const network = document.querySelector("input[name=network_interface]:checked")?.value || "offline";
  return { step: steps[index], language: $("language").value, keyboard: $("keyboard").value, network: { interface: network, offline: network === "offline" }, user: { display_name: $("display-name").value.trim(), username: $("username").value.trim() }, ai: { skipped: $("ai-skip").checked }, models: { skipped: $("model-skip").checked } };
}

async function save(values, complete = false) {
  $("save-status").textContent = "Saving locally...";
  await request(complete ? "/setup/complete" : "/setup/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
  $("save-status").textContent = "Saved locally";
}

$("setup-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("setup-error").hidden = true;
  try {
    const values = collect();
    if (steps[index] === "user" && values.user.username && !/^[a-z_][a-z0-9_-]{0,31}$/.test(values.user.username)) throw new Error("Use a valid username or leave it blank.");
    if (index === steps.length - 1) { await save(values, true); $("next-button").textContent = "Setup complete"; window.location.href = "/control-center"; return; }
    await save(values);
    index += 1;
    snapshot.state = { ...snapshot.state, ...values };
    render();
  } catch (error) { $("setup-error").textContent = error.message; $("setup-error").hidden = false; }
});

$("back-button").addEventListener("click", () => { if (index > 0) { index -= 1; render(); } });

(async function start() {
  try {
    snapshot = await request("/setup/state");
    if (snapshot.state.completed) { window.location.href = "/control-center"; return; }
    index = Math.max(0, steps.indexOf(snapshot.state.step));
    $("language").value = snapshot.state.language || "en_US";
    $("keyboard").value = snapshot.state.keyboard || "us";
    $("display-name").value = snapshot.state.user?.display_name || "";
    $("username").value = snapshot.state.user?.username || "";
    render();
  } catch (error) { $("setup-error").textContent = `Setup service unavailable: ${error.message}`; $("setup-error").hidden = false; }
})();
