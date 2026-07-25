const $ = (selector) => document.querySelector(selector);
let providers = [];

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

function renderProviders() {
  const body = $("#providers-body");
  body.innerHTML = providers.map((p) => `<tr>
    <td><span class="provider-name">${escapeHtml(p.name)}</span><span class="key-hint">${escapeHtml(p.key_hint)}</span></td>
    <td><span class="kind ${p.kind}">${kindLabel[p.kind]}</span></td>
    <td><span class="status"><i class="dot ${p.last_status}"></i>${statusLabel[p.last_status] || "未检测"}</span></td>
    <td>${p.priority}</td><td>${p.weight}</td><td class="latency">${p.last_latency_ms ? `${p.last_latency_ms} ms` : "—"}</td>
    <td><input class="toggle" type="checkbox" data-toggle="${p.id}" ${p.enabled ? "checked" : ""} aria-label="启用 ${escapeHtml(p.name)}"></td>
    <td><div class="row-actions"><button class="row-action" data-check="${p.id}" title="测试通道">◌</button><button class="row-action" data-edit="${p.id}" title="编辑">✎</button><button class="row-action" data-delete="${p.id}" title="删除">×</button></div></td>
  </tr>`).join("");
  $("#empty-providers").hidden = providers.length > 0;
  $("#provider-count").textContent = providers.length;
  $("#healthy-count").textContent = providers.filter((p) => p.last_status === "healthy").length;
}

async function loadProviders() {
  providers = await request("/api/providers");
  renderProviders();
}

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
  } else $("#provider-key").placeholder = "DeepL Key、DLX Token 或 Bearer Token";
  $("#provider-dialog").showModal();
}

async function saveProvider(event) {
  event.preventDefault();
  const id = $("#provider-id").value;
  const data = { name: $("#provider-name").value.trim(), kind: $("#provider-kind").value, endpoint: $("#provider-endpoint").value.trim(), api_key: $("#provider-key").value, priority: Number($("#provider-priority").value), weight: Number($("#provider-weight").value), timeout_seconds: Number($("#provider-timeout").value), enabled: $("#provider-enabled").checked };
  if (id && !data.api_key) delete data.api_key;
  try { await request(id ? `/api/providers/${id}` : "/api/providers", { method: id ? "PATCH" : "POST", body: JSON.stringify(data) }); $("#provider-dialog").close(); await loadProviders(); } catch (error) { alert(error.message); }
}

async function loadSettings() {
  const settings = await request("/api/settings");
  $("#fallback-enabled").checked = settings.fallback_enabled;
  $("#downstream-key").placeholder = settings.downstream_key_hint === "已设置" ? "已设置；留空则保持不变" : "留空仅用于本机开发";
}

async function testProvider(id) {
  const button = document.querySelector(`[data-check="${id}"]`);
  button.textContent = "…";
  try { const result = await request(`/api/providers/${id}/check`, { method: "POST" }); alert(result.ok ? `通道可用，${result.latency_ms} ms` : `检测失败：${result.error}`); } catch (error) { alert(error.message); } finally { await loadProviders(); }
}

async function testTranslation() {
  const status = $("#test-status");
  status.textContent = "正在请求路由…";
  $("#test-result").textContent = "";
  try {
    const result = await request("/translate", { method: "POST", body: JSON.stringify({ text: $("#test-text").value, source_lang: $("#test-source").value || null, target_lang: $("#test-target").value }) });
    $("#test-result").textContent = result.data;
    $("#test-provider").textContent = `由 ${result.providers[0]} 返回`;
    status.textContent = "请求成功";
  } catch (error) { status.textContent = error.message; $("#test-result").textContent = "请求未完成"; }
  await loadProviders();
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("button, input");
  if (!target) return;
  if (target.id === "add-provider") openProvider();
  if (target.dataset.closeDialog !== undefined) $("#provider-dialog").close();
  if (target.id === "refresh-providers") loadProviders();
  if (target.dataset.edit) openProvider(providers.find((p) => p.id === Number(target.dataset.edit)));
  if (target.dataset.check) testProvider(target.dataset.check);
  if (target.dataset.delete && confirm("确定删除此通道？")) { await request(`/api/providers/${target.dataset.delete}`, { method: "DELETE" }); await loadProviders(); }
  if (target.dataset.toggle) { await request(`/api/providers/${target.dataset.toggle}`, { method: "PATCH", body: JSON.stringify({ enabled: target.checked }) }); await loadProviders(); }
  if (target.id === "save-strategy") { await request("/api/settings", { method: "PUT", body: JSON.stringify({ fallback_enabled: $("#fallback-enabled").checked }) }); alert("路由策略已保存"); }
  if (target.id === "save-key") { const key = $("#downstream-key").value; const payload = key ? { downstream_key: key } : {}; await request("/api/settings", { method: "PUT", body: JSON.stringify(payload) }); $("#downstream-key").value = ""; await loadSettings(); alert("下游访问密钥已保存"); }
  if (target.id === "clear-key") { if (confirm("确定清除下游访问 Key？清除后客户端可不带 Key 访问接口。")) { await request("/api/settings", { method: "PUT", body: JSON.stringify({ downstream_key: "" }) }); $("#downstream-key").value = ""; await loadSettings(); alert("下游访问 Key 已清除"); } }
  if (target.id === "test-translation") testTranslation();
});

$("#provider-form").addEventListener("submit", saveProvider);
Promise.all([loadProviders(), loadSettings()]).catch((error) => { console.error(error); alert("无法连接到服务：" + error.message); });
