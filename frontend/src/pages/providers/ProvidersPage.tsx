import { Fragment, useMemo, useState, type FormEvent } from "react";
import {
  checkAllProviders,
  checkProvider,
  createProvider,
  createProvidersBatch,
  deleteProvider,
  deleteUnhealthy,
  disableUnhealthy,
  listProviders,
  queryAllQuota,
  queryProviderQuota,
  updateProvider,
} from "../../api/endpoints";
import type { Provider, ProviderInput, UpstreamKindMeta } from "../../api/types";
import HealthSparkline from "../../components/HealthSparkline";
import KindBadge from "../../components/KindBadge";
import Modal from "../../components/Modal";
import QuotaBadge from "../../components/QuotaBadge";
import Switch from "../../components/Switch";
import { useAsync } from "../../hooks/useAsync";
import { useUpstreamKinds } from "../../hooks/useUpstreamKinds";

type ProviderForm = Required<Omit<ProviderInput, "quota_limit">> & { quota_limit: string };

const blankForm = (meta?: UpstreamKindMeta): ProviderForm => ({
  name: "",
  kind: meta?.kind ?? "deepl",
  endpoint: meta?.default_endpoint ?? "https://api.deepl.com",
  api_key: "",
  api_secret: "",
  region: "",
  priority: 100,
  weight: 1,
  enabled: true,
  timeout_seconds: 20,
  quota_limit: "",
});

const fromProvider = (provider: Provider): ProviderForm => ({
  name: provider.name,
  kind: provider.kind,
  endpoint: provider.endpoint,
  api_key: "",
  api_secret: "",
  region: provider.region,
  priority: provider.priority,
  weight: provider.weight,
  enabled: provider.enabled,
  timeout_seconds: provider.timeout_seconds,
  quota_limit: provider.quota_limit == null ? "" : String(provider.quota_limit),
});

const statusText = (status: Provider["last_status"]) =>
  status === "healthy" ? "可用" : status === "unhealthy" ? "不可用" : "未检测";

export default function ProvidersPage() {
  const { data: providers, loading, error, reload } = useAsync(listProviders);
  const kinds = useUpstreamKinds();
  const [form, setForm] = useState<ProviderForm>(() => blankForm());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchLines, setBatchLines] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [collapsedKinds, setCollapsedKinds] = useState<Set<string>>(() => new Set());

  const metaByKind = useMemo(() => new Map(kinds.map((item) => [item.kind, item])), [kinds]);
  const groups = useMemo(() => {
    const grouped = new Map<string, Provider[]>();
    for (const provider of providers ?? []) {
      const group = grouped.get(provider.kind) ?? [];
      group.push(provider);
      grouped.set(provider.kind, group);
    }
    const entries: Array<[string, Provider[]]> = [...grouped.entries()];
    return entries.sort(([left], [right]) =>
      (metaByKind.get(left)?.sort_order ?? Number.MAX_SAFE_INTEGER) - (metaByKind.get(right)?.sort_order ?? Number.MAX_SAFE_INTEGER),
    );
  }, [metaByKind, providers]);
  const unhealthy = (providers ?? []).filter((provider) => provider.last_status === "unhealthy");

  const flash = (text: string) => {
    setMessage(text);
    window.setTimeout(() => setMessage(null), 3000);
  };

  const openCreate = () => {
    setEditingId(null);
    setForm(blankForm(kinds[0]));
    setFormOpen(true);
  };

  const openEdit = (provider: Provider) => {
    setEditingId(provider.id);
    setForm(fromProvider(provider));
    setFormOpen(true);
  };

  const changeKind = (kind: string) => {
    const meta = metaByKind.get(kind);
    setForm((current) => ({ ...current, kind, endpoint: meta?.default_endpoint ?? current.endpoint }));
  };

  const toggleGroup = (kind: string) => {
    setCollapsedKinds((current) => {
      const next = new Set(current);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  };

  const saveProvider = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload: ProviderInput = { ...form, quota_limit: form.quota_limit === "" ? null : Number(form.quota_limit) };
    if (editingId && !payload.api_key) delete payload.api_key;
    if (editingId && !payload.api_secret) delete payload.api_secret;
    setBusy("save");
    try {
      if (editingId) await updateProvider(editingId, payload);
      else await createProvider(payload);
      setFormOpen(false);
      await reload();
      flash(editingId ? "路由已更新" : "路由已添加");
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const runCheck = async (provider: Provider) => {
    setBusy(`check-${provider.id}`);
    try {
      const result = await checkProvider(provider.id);
      flash(result.ok ? `${provider.name} 可用（${result.latency_ms} ms）` : `${provider.name} 检测失败：${result.error ?? "未知错误"}`);
      await reload();
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const runBatchCheck = async () => {
    if (!providers?.length) return;
    setBusy("batch-check");
    try {
      const result = await checkAllProviders();
      await reload();
      flash(`批量检测完成：${result.healthy} 个可用，${result.unhealthy} 个不可用`);
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const toggleProvider = async (provider: Provider, enabled: boolean) => {
    setBusy(`toggle-${provider.id}`);
    try {
      await updateProvider(provider.id, { enabled });
      await reload();
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const removeProvider = async (provider: Provider) => {
    if (!window.confirm(`确定删除“${provider.name}”？此操作不可恢复。`)) return;
    setBusy(`delete-${provider.id}`);
    try {
      await deleteProvider(provider.id);
      await reload();
      flash("路由已删除");
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const refreshQuota = async (providerId?: number) => {
    setBusy(providerId ? `quota-${providerId}` : "quota-all");
    try {
      if (providerId) await queryProviderQuota(providerId);
      else await queryAllQuota();
      await reload();
      flash("额度信息已刷新");
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const handleUnhealthy = async (action: "disable" | "delete") => {
    if (!unhealthy.length) return;
    const actionLabel = action === "delete" ? "删除" : "禁用";
    if (!window.confirm(`确定${actionLabel} ${unhealthy.length} 个不可用路由？`)) return;
    setBusy(`unhealthy-${action}`);
    try {
      const ids = unhealthy.map((provider) => provider.id);
      const result = action === "delete" ? await deleteUnhealthy(ids) : await disableUnhealthy(ids);
      await reload();
      flash(`已${actionLabel} ${result.count} 个路由`);
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const importBatch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy("batch");
    try {
      const created = await createProvidersBatch({ lines: batchLines, priority: 100, weight: 1, timeout_seconds: 20 });
      setBatchOpen(false);
      setBatchLines("");
      await reload();
      flash(`已导入 ${created.length} 个路由`);
    } catch (reason) {
      flash(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const selectedMeta = metaByKind.get(form.kind);
  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon purple">↔</div>
          <div><h2>上游路由</h2><p>按优先级选择上游；同一优先级按照权重进行平滑轮询。</p></div>
          <div className="button-row">
            <button type="button" className="button" onClick={() => setBatchOpen(true)}>批量导入</button>
            <button type="button" className="button" disabled={busy === "batch-check" || !providers?.length} onClick={() => void runBatchCheck()}>{busy === "batch-check" ? "批量检测中…" : "批量检测"}</button>
            <button type="button" className="button" disabled={!unhealthy.length || busy === "unhealthy-disable"} onClick={() => void handleUnhealthy("disable")}>批量禁用 ({unhealthy.length})</button>
            <button type="button" className="button danger" disabled={!unhealthy.length || busy === "unhealthy-delete"} onClick={() => void handleUnhealthy("delete")}>批量删除 ({unhealthy.length})</button>
            <button type="button" className="button" disabled={busy === "quota-all"} onClick={() => void refreshQuota()}>刷新额度</button>
            <button type="button" className="button yellow" onClick={openCreate}>添加路由</button>
          </div>
        </div>
        {unhealthy.length > 0 && <div className="warning-bar">当前有 {unhealthy.length} 个不可用路由，可使用上方批量操作处理。</div>}
        {providers?.length ? (
          <div className="table-wrap"><table><thead><tr><th>名称 / 地址</th><th>类型</th><th>健康状态</th><th>优先级</th><th>额度</th><th>启用</th><th>操作</th></tr></thead><tbody>
            {groups.map(([kind, group]) => {
              const collapsed = collapsedKinds.has(kind);
              const meta = metaByKind.get(kind);
              return <Fragment key={kind}>
                <tr className="provider-group-row"><td colSpan={7}><button type="button" className="provider-group-toggle" aria-expanded={!collapsed} onClick={() => toggleGroup(kind)}><span className="group-chevron">{collapsed ? "▸" : "▾"}</span><strong className="provider-group-label">{meta?.label ?? kind}</strong><small>{group.length} 个路由</small></button></td></tr>
                {!collapsed && group.map((provider) => {
                  const providerMeta = metaByKind.get(provider.kind);
                  return <tr key={provider.id}>
                    <td><strong>{provider.name}</strong><div className="muted mono">{provider.endpoint}</div>{provider.last_error && <div className="error-text" title={provider.last_error}>{provider.last_error}</div>}</td>
                    <td><KindBadge kind={provider.kind} meta={providerMeta} /></td>
                    <td><div className="provider-health"><span className={`status-chip ${provider.last_status === "unhealthy" ? "bad" : ""}`}><i />{statusText(provider.last_status)}</span><HealthSparkline history={provider.health_history} latest={provider.last_status} /><span className="mono muted">{provider.last_latency_ms != null ? `${provider.last_latency_ms} ms` : ""}</span></div></td>
                    <td className="mono">{provider.priority} / {provider.weight}</td>
                    <td><QuotaBadge provider={provider} meta={providerMeta} querying={busy === `quota-${provider.id}`} onQuery={(id) => void refreshQuota(id)} /></td>
                    <td><Switch checked={provider.enabled} disabled={busy === `toggle-${provider.id}`} onChange={(enabled) => void toggleProvider(provider, enabled)} /></td>
                    <td><div className="button-row"><button type="button" className="button small" disabled={busy === `check-${provider.id}`} onClick={() => void runCheck(provider)}>检测</button><button type="button" className="button small" onClick={() => openEdit(provider)}>编辑</button><button type="button" className="button small danger" disabled={busy === `delete-${provider.id}`} onClick={() => void removeProvider(provider)}>删除</button></div></td>
                  </tr>;
                })}
              </Fragment>;
            })}
          </tbody></table></div>
        ) : <div className="empty-state">{loading ? "正在加载路由…" : error ? `加载失败：${error}` : "还没有上游路由。点击“添加路由”开始配置。"}</div>}
      </section>

      <Modal open={formOpen} onClose={() => setFormOpen(false)} eyebrow="UPSTREAM CONFIG" title={editingId ? "编辑路由" : "添加路由"}>
        <form onSubmit={(event) => void saveProvider(event)}>
          <div className="form-grid"><label>名称<input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="例如：主 DeepL 路由" /></label><label>上游类型<select value={form.kind} onChange={(event) => changeKind(event.target.value)}>{(kinds.length ? kinds : [{ kind: "deepl", label: "DeepL API" }]).map((kind) => <option key={kind.kind} value={kind.kind}>{kind.label}</option>)}</select></label></div>
          <label>服务地址<input required type="url" value={form.endpoint} onChange={(event) => setForm((current) => ({ ...current, endpoint: event.target.value }))} /><small>{selectedMeta?.endpoint_help}</small></label>
          <div className="form-grid"><label>{selectedMeta?.key_label ?? "API Key"}<input type="password" value={form.api_key} placeholder={editingId ? "留空以保留当前密钥" : selectedMeta?.key_placeholder} onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))} required={!editingId} /></label>{selectedMeta?.needs_secret && <label>{selectedMeta.secret_label}<input type="password" value={form.api_secret} placeholder={editingId ? "留空以保留当前密钥" : selectedMeta.secret_placeholder ?? "Secret Key"} onChange={(event) => setForm((current) => ({ ...current, api_secret: event.target.value }))} required={!editingId} /></label>}</div>
          {selectedMeta?.needs_region && <label>{selectedMeta.region_label}<input value={form.region} placeholder={selectedMeta.region_placeholder ?? "区域"} onChange={(event) => setForm((current) => ({ ...current, region: event.target.value }))} /></label>}
          <div className="form-grid three"><label>优先级<input min="1" max="10000" type="number" value={form.priority} onChange={(event) => setForm((current) => ({ ...current, priority: Number(event.target.value) }))} /></label><label>权重<input min="1" max="1000" type="number" value={form.weight} onChange={(event) => setForm((current) => ({ ...current, weight: Number(event.target.value) }))} /></label><label>超时（秒）<input min="2" max="120" type="number" value={form.timeout_seconds} onChange={(event) => setForm((current) => ({ ...current, timeout_seconds: Number(event.target.value) }))} /></label></div>
          {selectedMeta?.quota_type && <label>额度阈值（可选）<input min="0" type="number" value={form.quota_limit} onChange={(event) => setForm((current) => ({ ...current, quota_limit: event.target.value }))} placeholder={selectedMeta.quota_type === "characters" ? "字符数" : "余额"} /></label>}
          <div className="check-line"><Switch checked={form.enabled} onChange={(enabled) => setForm((current) => ({ ...current, enabled }))} /> 创建后立即启用</div>
          <div className="modal-actions"><button type="button" className="button ghost" onClick={() => setFormOpen(false)}>取消</button><button type="submit" className="button yellow" disabled={busy === "save"}>{busy === "save" ? "保存中…" : "保存路由"}</button></div>
        </form>
      </Modal>

      <Modal open={batchOpen} onClose={() => setBatchOpen(false)} eyebrow="BATCH IMPORT" title="批量导入路由"><form onSubmit={(event) => void importBatch(event)}><label>路由列表<textarea required value={batchLines} onChange={(event) => setBatchLines(event.target.value)} placeholder={"deepl | https://api-free.deepl.com | your-key:fx\ndlx | https://dlx.example.com | optional-token"} /><small>每行一条：类型 | URL | Key（可选）。支持 deepl、dlx、custom 等别名。</small></label><div className="modal-actions"><button type="button" className="button ghost" onClick={() => setBatchOpen(false)}>取消</button><button type="submit" className="button yellow" disabled={busy === "batch"}>{busy === "batch" ? "导入中…" : "导入路由"}</button></div></form></Modal>
      {message && <div className="toast" role="status">{message}</div>}
    </>
  );
}
