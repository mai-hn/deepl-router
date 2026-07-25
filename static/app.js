const $ = (selector) => document.querySelector(selector);
let providers = [];
let requestLogs = [];
let lastUnhealthyProviderIds = [];

const kindLabel = { deepl: "DeepL API", deeplx: "DeepLX / DLX", custom: "自定义 API" };
const statusLabel = { healthy: "可用", unhealthy: "不可用", unknown: "未检测" };

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败 (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function formatUsage(provider) {
  if (provider.kind !== "deepl") return "—";
  if (provider.usage_character_count == null || provider.usage_character_limit == null) {
    return `<button class="row-action quota-action" data-usage="${provider.id}">查询</button>`;
  }
  const limit = provider.usage_character_limit;
  const count = provider.usage_character_count;
  const percent = limit ? Math.min(100, Math.round((count / limit) * 100)) : 0;
  return `<button class="quota" data-usage="${provider.id}" title="点击刷新额度"><b>${percent}%</b><span>${count.toLocaleString()} / ${limit.toLocaleString()}</span></button>`;
}

function renderProviders() {
  $("#providers-body").innerHTML = providers.map((provider) => `<tr>
    <td><span class="provider-name">${escapeHtml(provider.name)}</span><span class="key-hint">${escapeHtml(provider.key_hint)}</span></td>
    <td><span class="kind ${provider.kind}">${kindLabel[provider.kind]}</span></td>
    <td><span class="status"><i class="dot ${provider.last_status}"></i>${statusLabel[provider.last_status] || "未检测"}</span></td>
    <td>${provider.priority}</td><td>${provider.weight}</td><td class="latency">${provider.last_latency_ms ? `${provider.last_latency_ms} ms` : "—"}</td><td>${formatUsage(provider)}</td>
    <td><input class="toggle" type="checkbox" data-toggle="${provider.id}" ${provider.enabled ? "checked" : ""} aria-label="启用 ${escapeHtml(provider.name)}"></td>
    <td><div class="row-actions"><button class="row-action" data-check="${provider.id}" title="测试路由">◌</button><button class="row-action" data-edit="${provider.id}" title="编辑">✎</button><button class="row-action" data-delete="${provider.id}" title="删除">×</button></div></td>
  </tr>`).join("");
  $("#empty-providers").hidden = providers.length > 0;
  $("#provider-count").textContent = providers.length;
  $("#healthy-count").textContent = providers.filter((provider) => provider.last_status === "healthy").length;
}

function formatTime(value) { return value ? value.replace("T", " ").replace("Z", "") : "—"; }
function statusTag(status) { return `<span class="log-status ${status}">${status === "success" ? "成功" : "失败"}</span>`; }

function renderLogs() {
  $("#logs-body").innerHTML = requestLogs.map((log) => `<tr>
    <td class="log-time">${formatTime(log.created_at)}</td><td>${statusTag(log.status)}</td><td><code>${escapeHtml(log.route)}</code></td>
    <td>${escapeHtml(log.provider || "—")}</td><td>${log.attempt_count}</td><td class="latency">${log.latency_ms ?? "—"} ms</td>
    <td class="log-preview" title="${escapeHtml(log.text_preview)}">${escapeHtml(log.text_preview || "—")}</td>
    <td><button class="row-action log-view" data-log="${log.id}">查看</button></td>
  </tr>`).join("");
  $("#empty-logs").hidden = requestLogs.length > 0;
}

async function loadProviders() { providers = await request("/api/providers"); renderProviders(); }
async function loadLogs() { requestLogs = await request("/api/logs"); renderLogs(); }

function providerDefaults() {
  $("#provider-id").value = "";
  $("#dialog-title").textContent = "添加路由";
  $("#provider-form").reset();
  $("#provider-priority").value = 100;
  $("#provider-weight").value = 1;
  $("#provider-timeout").value = 20;
  $("#provider-enabled").checked = true;
  $("#provider-kind").value = "deepl";
}

function openProvider(provider) {
  providerDefaults();
  if (provider) {
    $("#dialog-title").textContent = "编辑路由";
    $("#provider-id").value = provider.id;
    ["name", "kind", "endpoint", "priority", "weight", "timeout_seconds"].forEach((key) => { $("#provider-" + key.replace("timeout_seconds", "timeout")).value = provider[key]; });
    $("#provider-enabled").checked = provider.enabled;
    $("#provider-key").placeholder = "保持为空以保留当前 Key";
  }
  $("#provider-dialog").showModal();
}

function openBatchDialog() {
  $("#batch-form").reset();
  $("#batch-priority").value = 100;
  $("#batch-weight").value = 1;
  $("#batch-timeout").value = 20;
  $("#batch-dialog").showModal();
}

async function saveProvider(event) {
  event.preventDefault();
  const id = $("#provider-id").value;
  const data = { name: $("#provider-name").value.trim(), kind: $("#provider-kind").value, endpoint: $("#provider-endpoint").value.trim(), api_key: $("#provider-key").value, priority: Number($("#provider-priority").value), weight: Number($("#provider-weight").value), timeout_seconds: Number($("#provider-timeout").value), enabled: $("#provider-enabled").checked };
  if (id && !data.api_key) delete data.api_key;
  try { await request(id ? `/api/providers/${id}` : "/api/providers", { method: id ? "PATCH" : "POST", body: JSON.stringify(data) }); $("#provider-dialog").close(); await loadProviders(); } catch (error) { alert(error.message); }
}

async function saveBatch(event) {
  event.preventDefault();
  const payload = { lines: $("#batch-lines").value, priority: Number($("#batch-priority").value), weight: Number($("#batch-weight").value), timeout_seconds: Number($("#batch-timeout").value) };
  try {
    const created = await request("/api/providers/batch", { method: "POST", body: JSON.stringify(payload) });
    $("#batch-dialog").close();
    await loadProviders();
    alert(`已导入 ${created.length} 条路由`);
  } catch (error) { alert(error.message); }
}

async function loadSettings() {
  const settings = await request("/api/settings");
  $("#fallback-enabled").checked = settings.fallback_enabled;
  $("#downstream-key").placeholder = settings.downstream_key_hint === "已设置" ? "已设置；留空则保持不变" : "留空仅用于本机开发";
}

async function testProvider(id) {
  try { const result = await request(`/api/providers/${id}/check`, { method: "POST" }); alert(result.ok ? `路由可用，${result.latency_ms} ms` : `检测失败：${result.error}`); } catch (error) { alert(error.message); } finally { await loadProviders(); }
}

async function queryUsage(id) {
  try {
    const result = await request(`/api/providers/${id}/usage`, { method: "POST" });
    await loadProviders();
    alert(`额度：${result.character_count.toLocaleString()} / ${result.character_limit.toLocaleString()}`);
  } catch (error) { alert(error.message); }
}

async function queryAllUsage() {
  try {
    const results = await request("/api/usage", { method: "POST" });
    await loadProviders();
    const failed = results.filter((item) => !item.ok).length;
    alert(failed ? `已完成额度查询，${failed} 个路由失败` : `已完成 ${results.length} 个官方 DeepL 路由的额度查询`);
  } catch (error) { alert(error.message); }
}

function renderBatchCheckResult(result) {
  const container = $("#batch-check-result");
  lastUnhealthyProviderIds = result.results.filter((item) => !item.ok).map((item) => item.provider_id);
  container.hidden = false;
  container.innerHTML = `<div><b>批量检测完成</b><span>${result.healthy} 个可用 / ${result.unhealthy} 个不可用（共 ${result.total} 个）</span></div>${lastUnhealthyProviderIds.length ? `<div class="batch-check-actions"><button class="button outline" id="disable-unhealthy">禁用不可用路由（${lastUnhealthyProviderIds.length}）</button><button class="button danger" id="delete-unhealthy">删除不可用路由（${lastUnhealthyProviderIds.length}）</button></div>` : ""}`;
}

async function checkAllProviders() {
  const button = $("#batch-check");
  button.disabled = true;
  button.textContent = "检测中…";
  try {
    const result = await request("/api/providers/check", { method: "POST" });
    renderBatchCheckResult(result);
    await loadProviders();
  } catch (error) { alert(error.message); } finally {
    button.disabled = false;
    button.textContent = "批量检测";
  }
}

async function handleUnhealthyProviders(action) {
  if (!lastUnhealthyProviderIds.length) return;
  const isDelete = action === "delete";
  const message = isDelete ? `确定删除本次检测到的 ${lastUnhealthyProviderIds.length} 个不可用路由？此操作不可恢复。` : `确定禁用本次检测到的 ${lastUnhealthyProviderIds.length} 个不可用路由？`;
  if (!confirm(message)) return;
  try {
    const result = await request(`/api/providers/batch/${isDelete ? "delete" : "disable"}-unhealthy`, { method: "POST", body: JSON.stringify({ provider_ids: lastUnhealthyProviderIds }) });
    lastUnhealthyProviderIds = [];
    $("#batch-check-result").hidden = true;
    await loadProviders();
    alert(isDelete ? `已删除 ${result.count} 个不可用路由` : `已禁用 ${result.count} 个不可用路由`);
  } catch (error) { alert(error.message); }
}

async function testTranslation() {
  const status = $("#test-status");
  status.textContent = "正在请求路由…";
  try {
    const result = await request("/translate", { method: "POST", body: JSON.stringify({ text: $("#test-text").value, source_lang: $("#test-source").value || null, target_lang: $("#test-target").value }) });
    $("#test-result").textContent = result.data;
    $("#test-provider").textContent = `由 ${result.providers[0]} 返回`;
    status.textContent = "请求成功";
  } catch (error) { status.textContent = error.message; $("#test-result").textContent = "请求未完成"; }
  await Promise.all([loadProviders(), loadLogs()]);
}

async function openLog(logId) {
  const detail = await request(`/api/logs/${logId}`);
  $("#log-detail").textContent = JSON.stringify(detail, null, 2);
  $("#log-dialog").showModal();
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("button, input");
  if (!target) return;
  if (target.id === "add-provider") openProvider();
  if (target.id === "batch-provider") openBatchDialog();
  if (target.id === "batch-check") checkAllProviders();
  if (target.id === "refresh-usage") queryAllUsage();
  if (target.id === "disable-unhealthy") handleUnhealthyProviders("disable");
  if (target.id === "delete-unhealthy") handleUnhealthyProviders("delete");
  if (target.dataset.closeDialog !== undefined) $("#provider-dialog").close();
  if (target.dataset.closeBatch !== undefined) $("#batch-dialog").close();
  if (target.dataset.closeLog !== undefined) $("#log-dialog").close();
  if (target.id === "refresh-logs") loadLogs();
  if (target.dataset.edit) openProvider(providers.find((provider) => provider.id === Number(target.dataset.edit)));
  if (target.dataset.check) testProvider(target.dataset.check);
  if (target.dataset.usage) queryUsage(target.dataset.usage);
  if (target.dataset.log) openLog(target.dataset.log);
  if (target.dataset.delete && confirm("确定删除此路由？")) { await request(`/api/providers/${target.dataset.delete}`, { method: "DELETE" }); await loadProviders(); }
  if (target.dataset.toggle) { await request(`/api/providers/${target.dataset.toggle}`, { method: "PATCH", body: JSON.stringify({ enabled: target.checked }) }); await loadProviders(); }
  if (target.id === "save-strategy") { await request("/api/settings", { method: "PUT", body: JSON.stringify({ fallback_enabled: $("#fallback-enabled").checked }) }); alert("路由策略已保存"); }
  if (target.id === "save-key") { const key = $("#downstream-key").value; if (key) await request("/api/settings", { method: "PUT", body: JSON.stringify({ downstream_key: key }) }); $("#downstream-key").value = ""; await loadSettings(); alert("下游访问密钥已保存"); }
  if (target.id === "clear-key" && confirm("确定清除下游访问 Key？清除后客户端可不带 Key 访问接口。")) { await request("/api/settings", { method: "PUT", body: JSON.stringify({ downstream_key: "" }) }); $("#downstream-key").value = ""; await loadSettings(); alert("下游访问 Key 已清除"); }
  if (target.id === "test-translation") testTranslation();
});

$("#provider-form").addEventListener("submit", saveProvider);
$("#batch-form").addEventListener("submit", saveBatch);
Promise.all([loadProviders(), loadSettings(), loadLogs()]).catch((error) => { console.error(error); alert("无法连接到服务：" + error.message); });
