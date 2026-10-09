const $ = (selector) => document.querySelector(selector);
let contract;
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"})[char]);
const formatAssistantText = (value) => String(value).split("\n").map((line) => line.startsWith("## ") ? `<strong class="answer-heading">${escapeHtml(line.slice(3))}</strong>` : escapeHtml(line)).join("<br>");

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json", ...(options.headers || {})}, ...options});
  const payload = await response.json().catch(() => ({detail: "Non-JSON response"}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  return payload;
}

function show(target, html, error = false) {
  target.className = `result${error ? " error" : ""}`;
  target.innerHTML = html;
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab,.panel").forEach((el) => el.classList.remove("active"));
  tab.classList.add("active");
  $(`#${tab.dataset.panel}`).classList.add("active");
}));

async function initialize() {
  try {
    const [ready, version, loadedContract] = await Promise.all([api("/ready"), api("/version"), api("/contract")]);
    contract = loadedContract;
    $("#feature-json").value = JSON.stringify(contract.synthetic_example, null, 2);
    $("#health-dot").classList.add("ready");
    $("#health-label").textContent = ready.ready ? "All heads ready" : "Service degraded";
    $("#version-label").textContent = `API ${version.service_version} · model ${version.model_version}`;
  } catch (error) {
    $("#health-label").textContent = "Service unavailable";
    $("#version-label").textContent = error.message;
  }
  refreshMetrics();
}

$("#load-example").addEventListener("click", () => { if (contract) $("#feature-json").value = JSON.stringify(contract.synthetic_example, null, 2); });
$("#prediction-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const features = JSON.parse($("#feature-json").value);
    const result = await api("/predict", {method: "POST", body: JSON.stringify({features})});
    show($("#prediction-result"), `<div class="result-grid"><article><small>Return probability</small><strong>${(result.return_probability_90d * 100).toFixed(1)}%</strong></article><article><small>Campaign eligible</small><strong>${result.campaign_eligible ? "Yes" : "No"}</strong></article><article><small>Frozen threshold</small><strong>${result.threshold.toFixed(3)}</strong></article><article><small>Model version</small><strong>${result.model_version}</strong></article></div>`);
  } catch (error) { show($("#prediction-result"), `<strong>Prediction failed</strong><br>${escapeHtml(error.message)}`, true); }
});

$("#recommend-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const basket = $("#basket").value.split(",").map((v) => v.trim()).filter(Boolean);
    const result = await api("/recommend", {method: "POST", body: JSON.stringify({basket, k: Number($("#recommend-k").value)})});
    const rows = result.recommendations.map((r) => `<tr><td>${escapeHtml(r.item)}</td><td>${r.support?.toFixed(4) ?? "—"}</td><td>${r.confidence?.toFixed(3) ?? "—"}</td><td>${r.lift?.toFixed(2) ?? "—"}</td></tr>`).join("");
    show($("#recommend-result"), `<strong>Source: ${escapeHtml(result.source.replaceAll("_", " "))}</strong><table><thead><tr><th>Item</th><th>Support</th><th>Confidence</th><th>Lift</th></tr></thead><tbody>${rows}</tbody></table>`);
  } catch (error) { show($("#recommend-result"), `<strong>Recommendation failed</strong><br>${escapeHtml(error.message)}`, true); }
});

$("#assistant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await api("/chat", {method: "POST", body: JSON.stringify({question: $("#question").value, customer_verified: $("#customer-verified").checked})});
    const citations = result.citations.length ? `<p><small>Sources: ${result.citations.map((c) => `${escapeHtml(c.title)} (${escapeHtml(c.version)})`).join("; ")}</small></p>` : "";
    show($("#assistant-result"), `<p><strong>${escapeHtml(result.intent.replaceAll("_", " "))}</strong> · ${result.refused ? "Refused" : result.handoff ? "Handoff" : "Answered"}</p><p>${formatAssistantText(result.answer)}</p>${citations}`);
  } catch (error) { show($("#assistant-result"), `<strong>Assistant request failed</strong><br>${escapeHtml(error.message)}`, true); }
});

async function refreshMetrics() {
  try {
    const m = await api("/metrics");
    $("#metric-requests").textContent = m.requests_total;
    $("#metric-errors").textContent = m.errors_total;
    $("#metric-error-rate").textContent = `${(m.error_rate * 100).toFixed(1)}%`;
    $("#metric-latency").textContent = `${m.average_latency_ms.toFixed(1)} ms`;
    $("#alert-badge").textContent = m.alert_active ? "Alert active" : "Normal";
    $("#alert-badge").className = `badge ${m.alert_active ? "alert" : "good"}`;
  } catch (_) { $("#alert-badge").textContent = "Unavailable"; }
}

$("#normal-traffic").addEventListener("click", async () => {
  $("#traffic-status").textContent = "Generating normal traffic…";
  await Promise.all(Array.from({length: 8}, () => api("/health")));
  $("#traffic-status").textContent = "Normal traffic complete."; refreshMetrics();
});
$("#shifted-traffic").addEventListener("click", async () => {
  $("#traffic-status").textContent = "Generating intentionally invalid traffic…";
  await Promise.allSettled(Array.from({length: 8}, () => api("/predict", {method: "POST", body: JSON.stringify({features: {recency_days: -999}})})));
  $("#traffic-status").textContent = "Shifted traffic complete; invalid contracts were rejected as designed."; refreshMetrics();
});

initialize();
setInterval(refreshMetrics, 5000);
