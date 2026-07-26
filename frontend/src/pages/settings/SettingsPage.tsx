import { useEffect, useState } from "react";
import { getSettings, updateSettings } from "../../api/endpoints";
import { useAsync } from "../../hooks/useAsync";
import Switch from "../../components/Switch";

export default function SettingsPage() {
  const { data: settings, reload } = useAsync(getSettings);
  const [fallback, setFallback] = useState(true);
  const [key, setKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (settings) setFallback(settings.fallback_enabled);
  }, [settings]);

  const flash = (text: string) => {
    setMessage(text);
    window.setTimeout(() => setMessage(null), 2500);
  };

  const saveStrategy = async () => {
    try {
      await updateSettings({ fallback_enabled: fallback });
      flash("策略已保存");
      await reload();
    } catch (err) {
      flash(err instanceof Error ? err.message : String(err));
    }
  };

  const saveKey = async () => {
    try {
      await updateSettings({ downstream_key: key });
      setKey("");
      flash("下游 Key 已保存");
      await reload();
    } catch (err) {
      flash(err instanceof Error ? err.message : String(err));
    }
  };

  const clearKey = async () => {
    try {
      await updateSettings({ downstream_key: "" });
      setKey("");
      flash("下游 Key 已清除");
      await reload();
    } catch (err) {
      flash(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon green">▦</div>
          <div>
            <h2>路由策略</h2>
            <p>优先级数值越小越优先；同优先级通道使用平滑加权轮询</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            路由策略
            <select disabled>
              <option>加权轮询（推荐）</option>
            </select>
            <small>根据通道优先级与权重，平衡请求分配。</small>
          </label>
          <label>
            失败处理
            <select disabled>
              <option>自动回退</option>
            </select>
            <small>失败后尝试下一个候选通道。</small>
          </label>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 10, fontWeight: 800 }}>
            启用失败回退 <Switch checked={fallback} onChange={setFallback} />
          </span>
          <button type="button" className="button yellow" onClick={saveStrategy}>
            保存策略
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon purple">⚿</div>
          <div>
            <h2>下游访问 Key</h2>
            <p>
              下游客户端通过 <code>Authorization: Bearer &lt;key&gt;</code> 调用，留空则不校验（仅建议本机开发）
            </p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label style={{ flex: 1, minWidth: 240 }}>
            下游访问 Key（当前：{settings?.downstream_key_hint ?? "…"}）
            <input
              type="password"
              value={key}
              placeholder="留空仅用于本机开发"
              onChange={(event) => setKey(event.target.value)}
            />
          </label>
          <button type="button" className="button yellow" onClick={saveKey} disabled={!key}>
            保存 Key
          </button>
          <button type="button" className="button danger" onClick={clearKey}>
            清除 Key
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div className="heading-icon yellow">⇄</div>
          <div>
            <h2>接口信息</h2>
            <p>DeepL 兼容与沉浸式翻译格式的下游端点</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
          <span className="mono muted">DeepL 兼容</span>
          <code>POST /v2/translate</code>
          <span className="mono muted">沉浸式翻译</span>
          <code>POST /translate</code>
          <span className="mono muted">用量兼容</span>
          <code>GET /v2/usage</code>
        </div>
      </section>

      {message && (
        <div className="status-chip" role="status" style={{ position: "fixed", bottom: 24, right: 24, background: "var(--yellow)" }}>
          <i />
          {message}
        </div>
      )}
    </>
  );
}
