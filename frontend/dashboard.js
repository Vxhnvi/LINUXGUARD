/* LinuxGuard dashboard. All server data is inserted with textContent (never innerHTML) to avoid XSS. */
"use strict";
const $ = (id) => document.getElementById(id);
let pollMs = 5000, thresholds = {}, usageChart, netChart;

function token() { try { return sessionStorage.getItem("lg_token") || ""; } catch (e) { return ""; } }

async function api(path) {
  const headers = token() ? { "X-API-Key": token() } : {};
  const r = await fetch("/api/" + path, { headers });
  if (!r.ok) { const e = new Error("HTTP " + r.status); e.status = r.status; throw e; }
  return r.json();
}
function cell(tr, text, cls) { const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; tr.appendChild(td); return td; }
function fmtBytes(n) { const u = ["B","KB","MB","GB","TB"]; let i = 0; n = Number(n) || 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + " " + u[i]; }
function fmtUptime(s) { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return `${d}d ${h}h ${m}m`; }
function fmtTime(ts) { return new Date(ts * 1000).toLocaleString(); }
function level(metric, v) { const t = thresholds[metric]; if (!t) return ""; return v >= t.critical ? "critical" : v >= t.warning ? "warning" : ""; }

function setCard(cardId, valId, barId, subId, metric, pct, sub) {
  $(valId).textContent = pct.toFixed(1) + "%";
  $(barId).style.width = Math.min(pct, 100) + "%";
  $(subId).textContent = sub;
  $(cardId).className = "card " + level(metric, pct);
}
function showError(msg) { const b = $("errorBanner"); b.textContent = msg; b.hidden = !msg; }

async function refreshOverview() {
  const o = await api("overview");
  pollMs = Math.max(2, o.poll_seconds) * 1000;
  const s = o.system;
  $("hostname").textContent = s.hostname;
  const ov = $("overall"); ov.textContent = o.status; ov.className = "badge badge-" + o.status;
  const rows = [["Hostname", s.hostname], ["OS", s.os], ["Kernel", s.kernel], ["Architecture", s.architecture],
    ["CPU cores (logical / physical)", `${s.cpu_cores_logical} / ${s.cpu_cores_physical}`],
    ["Uptime", fmtUptime(s.uptime_seconds)], ["Boot time", fmtTime(s.boot_time)], ["Server time", fmtTime(o.server_time)],
    ["systemd", o.systemd_available ? "available" : "not available"]];
  const tb = $("infoTable").tBodies[0]; tb.replaceChildren();
  rows.forEach(([k, v]) => { const tr = document.createElement("tr"); cell(tr, k); cell(tr, String(v)); tb.appendChild(tr); });
}

async function refreshCurrent() {
  const cur = await api("metrics/current"); const m = cur.metrics;
  setCard("cardCpu", "cpuVal", "cpuBar", "cpuSub", "cpu", m.cpu_percent, `load avg: ${m.load1.toFixed(2)} / ${m.load5.toFixed(2)} / ${m.load15.toFixed(2)}`);
  setCard("cardMem", "memVal", "memBar", "memSub", "memory", m.mem_percent, `${fmtBytes(m.mem_used)} used of ${fmtBytes(m.mem_total)} (avail ${fmtBytes(m.mem_available)})`);
  setCard("cardDisk", "diskVal", "diskBar", "diskSub", "disk", m.disk_percent, `${fmtBytes(m.disk_used)} used, ${fmtBytes(m.disk_free)} free of ${fmtBytes(m.disk_total)}`);
  $("netVal").textContent = `▼ ${fmtBytes(m.net_recv_rate)}/s  ▲ ${fmtBytes(m.net_sent_rate)}/s`;
  $("netSub").textContent = `Total: ▼ ${fmtBytes(m.net_bytes_recv)}  ▲ ${fmtBytes(m.net_bytes_sent)}`;
  $("netPk").textContent = `Packets: ▼ ${m.net_packets_recv}  ▲ ${m.net_packets_sent}`;
  $("updated").textContent = new Date(m.ts * 1000).toLocaleTimeString();   // time of the sample itself
  return cur.stale ? `Monitoring data is stale (${Math.round(cur.age_seconds)} s old). Is the collector running?` : "";
}

function makeChart(canvasId, datasets, yMax) {
  return new Chart($(canvasId), { type: "line", data: { labels: [], datasets },
    options: { responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
      elements: { point: { radius: 0 }, line: { borderWidth: 2, tension: 0 } },
      scales: { x: { ticks: { color: "#8b949e", maxTicksLimit: 6 }, grid: { color: "#21262d" } },
        y: { min: 0, max: yMax, ticks: { color: "#8b949e" }, grid: { color: "#21262d" } } },
      plugins: { legend: { labels: { color: "#e6edf3" } } } } });
}
function ds(label, color) { return { label, data: [], borderColor: color, backgroundColor: color }; }

async function refreshCharts() {
  const minutes = $("range").value;
  const all = await api(`metrics/history?minutes=${minutes}&limit=300`);
  const pts = all.points, empty = pts.length < 2;
  $("usageEmpty").hidden = !empty; $("netEmpty").hidden = !empty;
  const withSeconds = Number(minutes) <= 60;   // short ranges need seconds to tell points apart
  const labels = pts.map(p => new Date(p.ts * 1000).toLocaleTimeString([], withSeconds ? { hour: "2-digit", minute: "2-digit", second: "2-digit" } : { hour: "2-digit", minute: "2-digit" }));
  usageChart.data.labels = labels;
  usageChart.data.datasets[0].data = pts.map(p => p.cpu_percent);
  usageChart.data.datasets[1].data = pts.map(p => p.mem_percent);
  usageChart.data.datasets[2].data = pts.map(p => p.disk_percent);
  usageChart.update();
  netChart.data.labels = labels;
  netChart.data.datasets[0].data = pts.map(p => p.net_recv_rate / 1024);
  netChart.data.datasets[1].data = pts.map(p => p.net_sent_rate / 1024);
  netChart.update();
}

async function refreshAlerts() {
  const { alerts } = await api("alerts?limit=50&status=" + $("alertFilter").value);
  const tb = $("alertTable").tBodies[0]; tb.replaceChildren();
  $("alertEmpty").hidden = alerts.length > 0;
  alerts.forEach(a => {
    const tr = document.createElement("tr");
    cell(tr, fmtTime(a.ts));
    const sev = cell(tr, ""); const sp = document.createElement("span"); sp.className = "sev sev-" + a.severity; sp.textContent = a.severity; sev.appendChild(sp);
    cell(tr, a.message); cell(tr, a.status === "active" ? "ACTIVE" : "resolved", a.status === "active" ? "st-no" : "st-yes");
    tb.appendChild(tr);
  });
}

async function refreshProcesses() {
  const msg = $("procMsg"), tb = $("procTable").tBodies[0];
  try {
    const { processes } = await api("processes?limit=15&sort=" + $("procSort").value);
    msg.hidden = true; tb.replaceChildren();
    processes.forEach(p => { const tr = document.createElement("tr");
      cell(tr, p.pid); cell(tr, p.name); cell(tr, p.user || "—"); cell(tr, p.cpu_percent == null ? "—" : p.cpu_percent.toFixed(1)); cell(tr, p.memory_percent == null ? "—" : p.memory_percent.toFixed(2)); cell(tr, p.status); tb.appendChild(tr); });
  } catch (e) { tb.replaceChildren(); msg.hidden = false; msg.textContent = e.status === 401 ? "Protected endpoint — click “API token” and enter your token." : "Could not load processes."; }
}

async function refreshServices() {
  const msg = $("svcMsg"), tb = $("svcTable").tBodies[0];
  try {
    const d = await api("services"); tb.replaceChildren();
    msg.hidden = d.systemd_available; msg.textContent = d.message;
    d.services.forEach(s => { const tr = document.createElement("tr");
      cell(tr, s.name); cell(tr, s.state, "st-" + (s.state === "active" ? "active" : s.state === "failed" ? "failed" : "inactive")); cell(tr, s.running ? "yes" : "no", s.running ? "st-yes" : "st-no"); tb.appendChild(tr); });
  } catch (e) { tb.replaceChildren(); msg.hidden = false; msg.textContent = e.status === 401 ? "Protected endpoint — set your API token." : "Could not load services."; }
}

async function tick() {
  try {
    const results = await Promise.all([refreshCurrent(), refreshOverview(), refreshCharts(), refreshAlerts(), refreshProcesses(), refreshServices()]);
    showError(results[0]);   // empty string hides the banner; non-empty = stale-data warning
  } catch (e) {
    showError("Cannot reach the LinuxGuard API (" + e.message + "). Retrying…");
    $("overall").textContent = "offline"; $("overall").className = "badge badge-unknown";
  }
  setTimeout(tick, pollMs);
}

async function init() {
  usageChart = makeChart("usageChart", [ds("CPU", "#58a6ff"), ds("Memory", "#bc8cff"), ds("Disk", "#d29922")], 100);
  netChart = makeChart("netChart", [ds("Received", "#3fb950"), ds("Sent", "#f85149")]);
  try { thresholds = (await api("thresholds")).thresholds; } catch (e) { /* cards just won't colour */ }
  $("range").onchange = refreshCharts; $("alertFilter").onchange = refreshAlerts; $("procSort").onchange = refreshProcesses;
  $("tokenBtn").onclick = () => { const t = prompt("API token (kept in this tab only):", token()); if (t !== null) { try { sessionStorage.setItem("lg_token", t.trim()); } catch (e) {} refreshProcesses(); refreshServices(); } };
  tick();
}
init();
