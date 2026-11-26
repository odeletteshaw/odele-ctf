const $ = (id) => document.getElementById(id);
const STATUS_LABEL = {
  running: "进行中", preparing: "准备中", solved: "已解",
  done: "失败", failed: "失败", error: "错误", cancelled: "已停止", idle: "待命",
};
const DIRS = ["web", "crypto", "misc", "forensics"];

let sessions = [];
let autosolving = false;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(j.error || r.statusText);
  }
  return r.json();
}

function stClass(st) {
  return "st-" + (st || "idle");
}

function render() {
  const tb = $("tbody");
  tb.innerHTML = "";
  sessions.forEach((s) => {
    const tr = document.createElement("tr");
    const actions = [];
    actions.push(`<button class="small" onclick="viewDetail(${s.id})">查看</button>`);
    if (s.is_running) {
      actions.push(`<button class="small danger" onclick="stopSession(${s.id})">停止</button>`);
    } else if (["done", "failed", "error", "cancelled"].includes(s.status)) {
      actions.push(`<button class="small" onclick="retrySession(${s.id})">重试</button>`);
    }
    actions.push(`<button class="small danger" onclick="delSession(${s.id})">删除</button>`);
    tr.innerHTML = `
      <td class="muted">${s.id}</td>
      <td class="muted">${s.category || ""}</td>
      <td>${s.title || ""}</td>
      <td class="${stClass(s.status)}">${STATUS_LABEL[s.status] || s.status}</td>
      <td class="muted">${s.created_at || "—"}</td>
      <td><div class="actions">${actions.join("")}</div></td>`;
    tb.appendChild(tr);
  });
  $("btnAuto").textContent = autosolving ? "⏹ 停止打题" : "▶ 开始打题";
  $("status").textContent = `${sessions.length} 个 session`;
}

async function refresh() {
  sessions = await api("/api/sessions");
  const st = await api("/api/status");
  autosolving = st.is_autosolving;
  render();
  loadSlots();
}

async function loadSlots() {
  try {
    const slots = await api("/api/autosolve/slots");
    if (slots.length) {
      const parts = slots.map((s) =>
        `${s.direction}·t${s.token_index} ${s.running ? s.phase + (s.current_title ? ":" + s.current_title : "") : "停"}`);
      $("status").textContent = `${sessions.length} 个 session · ${parts.join(" | ")}`;
    }
  } catch (e) {}
}

// ---- autosolve -----------------------------------------------------------
function openAuto() {
  if (autosolving) { stopAutosolve(); return; }
  const box = $("dirChecks");
  box.innerHTML = DIRS.map((d) =>
    `<label><input type="checkbox" value="${d}"> ${d}</label>`).join("");
  fetchTokens();
  $("autoModal").classList.add("open");
}
async function fetchTokens() {
  try {
    const st = await api("/api/status");
    $("autoInfo").textContent = "";
  } catch (e) {}
}
async function startAutosolve() {
  const dirs = [...document.querySelectorAll("#dirChecks input:checked")].map((c) => c.value);
  if (!dirs.length) { alert("至少勾选一个方向"); return; }
  const diff = $("diffSel").value;
  const max = parseInt($("maxInput").value || "0", 10) || 0;
  await api("/api/autosolve/start", {
    method: "POST",
    body: JSON.stringify({ directions: dirs, max, difficulty: diff ? { "简单": "Easy", "中等": "Medium", "困难": "Hard" }[diff] : null }),
  });
  $("autoModal").classList.remove("open");
  refresh();
}
async function stopAutosolve() {
  await api("/api/autosolve/stop", { method: "POST" });
  refresh();
}

// ---- session actions -----------------------------------------------------
async function stopSession(id) { await api(`/api/sessions/${id}/stop`, { method: "POST" }); refresh(); }
async function delSession(id) {
  if (!confirm("删除这个 session？")) return;
  await api(`/api/sessions/${id}/delete`, { method: "POST" }); refresh();
}
async function retrySession(id) {
  if (!confirm("重新解这道题？")) return;
  await api(`/api/sessions/${id}/retry`, { method: "POST" }); refresh();
}
async function batchDelete() {
  if (!confirm("删除所有失败的 session？")) return;
  const r = await api("/api/sessions/batch_delete", { method: "POST" });
  alert(`删除了 ${r.deleted} 个`);
  refresh();
}

// ---- detail --------------------------------------------------------------
let detail = null;
async function viewDetail(id) {
  detail = await api(`/api/sessions/${id}`);
  $("detailTitle").textContent = `${detail.title} · ${detail.category}`;
  $("detailStatus").textContent = STATUS_LABEL[detail.status] || detail.status;
  $("detailFlag").textContent = detail.flag || "—";
  const tabs = ["Findings", "Thinking", "题解"];
  $("detailTabs").innerHTML = tabs.map((t, i) =>
    `<button class="small" style="margin-right:6px" onclick="showTab(${i})">${t}</button>`).join("");
  showTab(0);
  $("detailModal").classList.add("open");
}
function showTab(i) {
  let text = "—";
  if (i === 0) text = (detail.paths || []).map((p) => "- " + p).join("\n") || "—";
  else if (i === 1) text = detail.thinking || "—";
  else text = detail.writeup || "（未生成）";
  $("detailBody").textContent = text;
}

// ---- wire up -------------------------------------------------------------
$("btnAuto").addEventListener("click", openAuto);
$("btnBatchDelete").addEventListener("click", batchDelete);
$("autoStart").addEventListener("click", startAutosolve);
$("autoCancel").addEventListener("click", () => $("autoModal").classList.remove("open"));
$("detailClose").addEventListener("click", () => $("detailModal").classList.remove("open"));

refresh();

// WebSocket for live refresh
function connectWs() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => { if (JSON.parse(e.data).type === "changed") refresh(); };
  ws.onclose = () => setTimeout(connectWs, 2000);
}
connectWs();
setInterval(refresh, 5000);

// ---- memory pool (通话池) ------------------------------------------------
function showView(name) {
  $("ctfView").style.display = name === "ctf" ? "block" : "none";
  $("memView").style.display = name === "mem" ? "block" : "none";
  $("manualView").style.display = name === "manual" ? "block" : "none";
  $("configView").style.display = name === "config" ? "block" : "none";
  $("teamView").style.display = name === "team" ? "block" : "none";
  $("navCtf").classList.toggle("active", name === "ctf");
  $("navMem").classList.toggle("active", name === "mem");
  $("navManual").classList.toggle("active", name === "manual");
  $("navConfig").classList.toggle("active", name === "config");
  $("navTeam").classList.toggle("active", name === "team");
  if (name === "mem") loadMemories("");
  if (name === "config") loadConfig();
  if (name === "team") loadTeam();
}

async function loadMemories(q) {
  let url = "/api/memories";
  if (q) url = `/api/memories/search?q=${encodeURIComponent(q)}`;
  const mems = await api(url);
  $("memCount").textContent = `${mems.length} 条记忆`;
  $("memList").innerHTML = mems.map((m) => `
    <div style="background:var(--panel);border-radius:8px;padding:14px 16px;margin-bottom:10px">
      <div style="margin-bottom:6px">
        <strong>${m.title || ""}</strong>
        <span class="muted" style="margin-left:8px">${m.category || ""}</span>
        <span class="muted" style="margin-left:8px;font-size:12px">${m.source || ""}</span>
      </div>
      <pre style="margin:0;max-height:260px;overflow:auto">${m.content || ""}</pre>
    </div>`).join("");
}

$("memSearchBtn").addEventListener("click", () => loadMemories($("memSearch").value.trim()));
$("memSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") loadMemories($("memSearch").value.trim()); });

// ---- manual solve --------------------------------------------------------
async function startManual() {
  const direction = $("manDir").value;
  const urls = $("manUrls").value.split("\n").map((s) => s.trim()).filter(Boolean);
  if (direction === "web" && !urls.length) { alert("web 至少填一个 URL"); return; }
  const spec = {
    kind: "custom", category: direction,
    urls: direction === "web" ? urls : [],
    description: $("manDesc").value.trim(),
    flag_prefix: $("manPrefix").value.trim() || "flag",
    attachments: [],
    max_turns: parseInt($("manTurns").value || "100", 10),
  };
  const title = urls[0] ? urls[0].split("/")[2] : direction;
  await api("/api/manual", { method: "POST", body: JSON.stringify({ spec, title }) });
  showView("ctf"); refresh();
}

// ---- config --------------------------------------------------------------
async function loadConfig() {
  const c = await api("/api/config");
  $("configBody").textContent =
    `模型:        ${c.model}\n` +
    `API Base:    ${c.api_base}\n` +
    `API Key:     ${c.api_key}\n` +
    `API 超时:    ${c.api_timeout}s\n` +
    `Agent token: ${c.tokens} 个\n` +
    `失败黑名单:  ${c.failed_count} 道\n` +
    `记忆池:      ${c.memory_count} 条`;
}
async function clearFailed() {
  if (!confirm("清空失败黑名单？")) return;
  const r = await api("/api/config/clear_failed", { method: "POST" });
  alert(`清除了 ${r.cleared} 条`);
  loadConfig();
}

$("manStart").addEventListener("click", startManual);
$("clearFailed").addEventListener("click", clearFailed);

// ---- team ----------------------------------------------------------------
async function loadTeam() {
  const t = await api("/api/team");
  const members = t.members || [];
  $("teamList").innerHTML = members.map((m) => `
    <div style="display:flex;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid #1f2735">
      <strong>${m.name || ""}</strong>
      <span class="muted">token ${m.token_index}</span>
      <span>${(m.directions || []).join(", ") || "—"}</span>
    </div>`).join("");
  $("teamJson").value = JSON.stringify(t, null, 2);
}
async function saveTeam() {
  try {
    const members = JSON.parse($("teamJson").value).members;
    if (!Array.isArray(members)) throw new Error("members 必须是数组");
    await api("/api/team", { method: "POST", body: JSON.stringify({ members }) });
    loadTeam();
    alert("团队已保存");
  } catch (e) {
    alert("JSON 解析失败: " + e.message);
  }
}
$("teamSave").addEventListener("click", saveTeam);
